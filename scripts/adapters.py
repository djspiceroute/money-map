#!/usr/bin/env python3
"""
Source adapters for the money-map skill.

Every financial input (bank CSV, finance-app export, Plaid pull) is converted
into ONE canonical transaction schema so the rest of the pipeline never has to
care where a row came from.

CANONICAL SCHEMA (one row per transaction):
    date         YYYY-MM-DD
    description  merchant / memo text
    amount       SIGNED float. NEGATIVE = money out (spend), POSITIVE = money in.
    account      human account/card name (e.g. "Apple Card", "Chase Checking")
    institution  bank / provider (e.g. "Apple", "Chase")
    category     source-provided category (may be blank; enrichment fills gaps)
    source       which input this came from (adapter id or file label)

The hard part of ingesting financial data is that every exporter uses different
column names, date formats, and sign conventions. An "adapter" is just a small
description of how ONE source's columns map onto the schema above. Add a new
exporter by adding one dict to ADAPTERS - no other code changes needed.

This module is intentionally dependency-free (Python stdlib only) so a
non-technical user can run it with the system Python.
"""
import csv, re, io, datetime

# ---------------------------------------------------------------------------
# Built-in adapters. Each adapter is keyed by an id and describes:
#   signature : header names that identify this format (lowercased substrings).
#               All must be present for auto-detection to pick this adapter.
#   date      : source column holding the date
#   desc      : source column holding the description/merchant
#   amount    : source column holding a single signed/unsigned amount   (mode A)
#   outflow/inflow : two-column money out/in (YNAB style)               (mode B)
#   debit/credit   : two-column debit/credit (some banks)              (mode B)
#   type_col + type_debit_values : a "transaction type" column whose value
#               tells us the sign (Mint style)                          (mode C)
#   sign      : "as_is"  -> negative already means spend
#               "invert" -> source uses positive=spend, so multiply by -1
#               "abs_by_type" -> use type/outflow columns to decide sign
#   category  : source column for category (optional)
#   account   : source column for account, OR a fixed string if account_fixed
#   account_fixed / institution_fixed : constant when the file is one account
# ---------------------------------------------------------------------------
ADAPTERS = {
    "apple_card": {
        "label": "Apple Card (card.apple.com export)",
        "signature": ["transaction date", "merchant", "amount (usd)"],
        "date": "Transaction Date", "desc": "Merchant", "amount": "Amount (USD)",
        "category": "Category", "sign": "invert",
        "account_fixed": "Apple Card", "institution_fixed": "Apple",
    },
    "copilot": {
        "label": "Copilot Money export",
        "signature": ["date", "name", "amount", "category", "account"],
        "date": "date", "desc": "name", "amount": "amount",
        "category": "category", "account": "account", "sign": "as_is",
    },
    "mint": {
        "label": "Mint / Intuit export",
        "signature": ["date", "description", "amount", "transaction type"],
        "date": "Date", "desc": "Description", "amount": "Amount",
        "category": "Category", "account": "Account Name",
        "type_col": "Transaction Type", "type_debit_values": ["debit"],
        "sign": "abs_by_type",
    },
    "monarch": {
        "label": "Monarch Money export",
        "signature": ["date", "merchant", "category", "account", "amount"],
        "date": "Date", "desc": "Merchant", "amount": "Amount",
        "category": "Category", "account": "Account", "sign": "as_is",
    },
    "ynab": {
        "label": "YNAB register export",
        "signature": ["date", "payee", "outflow", "inflow"],
        "date": "Date", "desc": "Payee", "category": "Category",
        "account": "Account", "outflow": "Outflow", "inflow": "Inflow",
        "sign": "abs_by_type",
    },
    "plaid": {
        "label": "Plaid CLI export (already canonical-ish)",
        "signature": ["date", "description", "amount", "account", "institution"],
        "date": "Date", "desc": "Description", "amount": "Amount",
        "category": "Category", "account": "Account", "institution": "Institution",
        "sign": "as_is",
    },
    # Generic fallback for plain bank CSVs with a single Amount column.
    "generic_amount": {
        "label": "Generic bank CSV (Date / Description / Amount)",
        "signature": ["date", "amount"],
        "date": "Date", "desc": "Description", "amount": "Amount",
        "category": "Category", "sign": "as_is",
    },
    # Generic fallback for bank CSVs that split Debit and Credit columns.
    "generic_debit_credit": {
        "label": "Generic bank CSV (Debit / Credit columns)",
        "signature": ["date", "debit", "credit"],
        "date": "Date", "desc": "Description",
        "debit": "Debit", "credit": "Credit", "sign": "abs_by_type",
    },
}

# Common header aliases so a column called "Posting Date" still maps to date, etc.
ALIASES = {
    "date": ["date", "transaction date", "posting date", "posted date", "trans date"],
    "desc": ["description", "merchant", "name", "payee", "memo", "details", "transaction"],
    "amount": ["amount", "amount (usd)", "amt"],
    "category": ["category", "categories"],
    "subcategory": ["subcategory", "sub category", "sub-category", "detailed category"],
    "account": ["account", "account name", "card", "account name/number"],
    "institution": ["institution", "bank", "financial institution"],
    "debit": ["debit", "withdrawal", "withdrawals", "money out"],
    "credit": ["credit", "deposit", "deposits", "money in"],
    "outflow": ["outflow"],
    "inflow": ["inflow"],
    "type_col": ["transaction type", "type"],
}


def _norm(s):
    return (s or "").strip().lower()


def detect_adapter(headers):
    """Return the best-matching adapter id for a list of CSV headers, or None."""
    hl = [_norm(h) for h in headers]
    hset = set(hl)
    best, best_score = None, 0
    # Prefer the most specific signature (most columns matched).
    order = ["apple_card", "mint", "ynab", "monarch", "copilot", "plaid",
             "generic_debit_credit", "generic_amount"]
    for aid in order:
        sig = ADAPTERS[aid]["signature"]
        if all(any(s in h for h in hset) for s in sig):
            if len(sig) > best_score:
                best, best_score = aid, len(sig)
    return best


def _find_col(headers, wanted, adapter_key):
    """Resolve the actual header for a logical field, tolerating name variants."""
    hmap = {_norm(h): h for h in headers}
    # 1) exact configured name
    if wanted and _norm(wanted) in hmap:
        return hmap[_norm(wanted)]
    # 2) alias list for this logical field
    for alias in ALIASES.get(adapter_key, []):
        if alias in hmap:
            return hmap[alias]
    return None


def parse_amount(raw):
    if raw is None:
        return None
    s = str(raw).strip()
    if s == "":
        return None
    neg = s.startswith("(") and s.endswith(")")  # (123.45) accounting negatives
    s = s.replace("(", "").replace(")", "")
    s = s.replace("$", "").replace(",", "").replace("USD", "").strip()
    if s in ("", "-", "--"):
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


_DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y", "%m-%d-%Y",
                 "%Y/%m/%d", "%b %d, %Y", "%d %b %Y", "%m/%d/%Y %H:%M",
                 "%Y-%m-%dT%H:%M:%S"]


def parse_date(raw):
    s = str(raw or "").strip()
    if not s:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.datetime.strptime(s[:len(fmt) + 4], fmt).date().isoformat()
        except ValueError:
            continue
    # last resort: pull a YYYY-MM-DD or MM/DD/YYYY out of the string
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", s)
    if m:
        mo, da, yr = m.groups()
        yr = ("20" + yr) if len(yr) == 2 else yr
        return f"{yr}-{int(mo):02d}-{int(da):02d}"
    return None


def apply_adapter(headers, rows, adapter_id, source_label=None,
                  account_override=None, institution_override=None):
    """Convert raw rows (list of dicts) into canonical rows using an adapter."""
    a = ADAPTERS[adapter_id]
    src = source_label or adapter_id
    c_date = _find_col(headers, a.get("date"), "date")
    c_desc = _find_col(headers, a.get("desc"), "desc")
    c_amt = _find_col(headers, a.get("amount"), "amount")
    c_cat = _find_col(headers, a.get("category"), "category")
    c_sub = _find_col(headers, a.get("subcategory"), "subcategory")
    c_acct = _find_col(headers, a.get("account"), "account")
    c_inst = _find_col(headers, a.get("institution"), "institution")
    c_debit = _find_col(headers, a.get("debit"), "debit")
    c_credit = _find_col(headers, a.get("credit"), "credit")
    c_out = _find_col(headers, a.get("outflow"), "outflow")
    c_in = _find_col(headers, a.get("inflow"), "inflow")
    c_type = _find_col(headers, a.get("type_col"), "type_col")
    sign = a.get("sign", "as_is")
    debit_vals = [v.lower() for v in a.get("type_debit_values", [])]

    out = []
    for r in rows:
        date = parse_date(r.get(c_date)) if c_date else None
        if not date:
            continue
        desc = (r.get(c_desc) or "").strip() if c_desc else ""

        # ---- resolve a signed amount ----
        amount = None
        if sign == "abs_by_type":
            if c_out or c_in:                       # YNAB-style two columns
                o = parse_amount(r.get(c_out)) or 0
                i = parse_amount(r.get(c_in)) or 0
                amount = (i or 0) - (o or 0)        # in positive, out negative
            elif c_debit or c_credit:               # debit/credit two columns
                d = parse_amount(r.get(c_debit)) or 0
                cr = parse_amount(r.get(c_credit)) or 0
                amount = (cr or 0) - (d or 0)
            elif c_type and c_amt:                  # Mint-style type column
                v = parse_amount(r.get(c_amt))
                if v is None:
                    continue
                t = _norm(r.get(c_type))
                amount = -abs(v) if t in debit_vals else abs(v)
        else:
            v = parse_amount(r.get(c_amt)) if c_amt else None
            if v is None:
                continue
            amount = -v if sign == "invert" else v
        if amount is None:
            continue

        # category + subcategory. Many exporters encode a hierarchy in one
        # field ("Food and Drink > Restaurants > Fast Food"); split it so the
        # top level is the category and the remainder is the subcategory.
        cat_raw = (r.get(c_cat) or "").strip() if c_cat else ""
        sub_raw = (r.get(c_sub) or "").strip() if c_sub else ""
        if not sub_raw and (">" in cat_raw):
            parts = [p.strip() for p in cat_raw.split(">") if p.strip()]
            cat_raw = parts[0] if parts else cat_raw
            sub_raw = " / ".join(parts[1:])

        out.append({
            "date": date,
            "description": desc,
            "amount": round(amount, 2),
            "account": account_override or (r.get(c_acct).strip() if c_acct and r.get(c_acct) else a.get("account_fixed", "")),
            "institution": institution_override or (r.get(c_inst).strip() if c_inst and r.get(c_inst) else a.get("institution_fixed", "")),
            "category": cat_raw,
            "subcategory": sub_raw,
            "source": src,
        })
    return out


def read_csv(path):
    """Read a CSV, skipping any leading junk lines before the real header."""
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        text = f.read()
    # find the line that looks most like a header (has date + amount-ish words)
    lines = text.splitlines()
    start = 0
    for i, ln in enumerate(lines[:15]):
        low = ln.lower()
        if ("date" in low) and ("amount" in low or "debit" in low or "outflow" in low or "merchant" in low):
            start = i
            break
    reader = csv.DictReader(io.StringIO("\n".join(lines[start:])))
    rows = list(reader)
    return reader.fieldnames or [], rows


CANON_FIELDS = ["date", "description", "amount", "account", "institution", "category", "subcategory", "source"]
