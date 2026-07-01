#!/usr/bin/env python3
"""
plaid_to_csv.py - convert a Plaid CLI JSON dump into a canonical CSV.

The official Plaid CLI can export transactions as JSON:

    plaid transactions list --all --start-date 2024-01-01 --end-date 2026-06-30 \
        --count 500 --json > plaid_dump.json

That JSON looks like: { "items": [ { "item": {...}, "accounts": [...],
"transactions": [...] }, ... ] }. This script flattens it to the canonical
schema and, crucially, FIXES THE SIGN: Plaid uses positive = money out, which
is the opposite of our convention, so amounts are inverted here.

Usage:
    python plaid_to_csv.py plaid_dump.json --out plaid_canonical.csv

Notes for the assistant helping a user:
  - Plaid's trial/dev tier often returns only ~90 days of history.
  - Auto loans return a balance but NOT apr/min-payment/due (cards do).
  - Account names from Plaid are sometimes generic ("CREDIT CARD"); use the
    account_aliases config in enrichment to rename them.
"""
import argparse, csv, json

FIELDS = ["date", "description", "amount", "account", "institution", "category", "subcategory", "source"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--out", default="plaid_canonical.csv")
    args = ap.parse_args()

    data = json.load(open(args.dump))
    items = data.get("items", data if isinstance(data, list) else [data])
    rows = []
    for it in items:
        inst = (it.get("item", {}) or {}).get("institution_name") or it.get("institution") or "Plaid"
        acct_names = {}
        for a in it.get("accounts", []):
            acct_names[a.get("account_id")] = a.get("name") or a.get("official_name") or "Account"
        for t in it.get("transactions", []):
            amt = t.get("amount")
            if amt is None:
                continue
            cat, sub = "", ""
            pf = t.get("personal_finance_category") or {}
            if isinstance(pf, dict):
                cat = pf.get("primary") or ""
                det = pf.get("detailed") or ""
                # detailed is like "FOOD_AND_DRINK_RESTAURANTS"; keep the tail as subcategory
                if det and cat and det.startswith(cat):
                    sub = det[len(cat):].strip("_").replace("_", " ").title()
            if isinstance(t.get("category"), list) and t["category"]:
                if not cat:
                    cat = t["category"][0]
                if not sub and len(t["category"]) > 1:
                    sub = " / ".join(t["category"][1:])
            rows.append({
                "date": (t.get("date") or "")[:10],
                "description": t.get("merchant_name") or t.get("name") or "",
                "amount": round(-float(amt), 2),   # INVERT: Plaid +out -> -spend
                "account": acct_names.get(t.get("account_id"), ""),
                "institution": inst,
                "category": cat,
                "subcategory": sub,
                "source": "plaid",
            })
    rows = [r for r in rows if r["date"]]
    rows.sort(key=lambda r: r["date"])
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print("WROTE %s (%d transactions)" % (args.out, len(rows)))


if __name__ == "__main__":
    main()
