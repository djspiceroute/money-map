#!/usr/bin/env python3
"""
enrich.py - categorize, alias accounts, detect recurring charges, and summarize
balances from a canonical/deduped transaction CSV.

Everything is dependency-free and driven by small CSV config files:
merchant_categories.csv, account_aliases.csv, recurring_labels.csv, and
manual_balances.csv. The default config paths point at the repo's synthetic
example files so the public sample pipeline runs end to end.
"""
import argparse, csv, datetime, json, math, os, re, statistics

BASE_FIELDS = ["date", "description", "amount", "account", "institution",
               "category", "subcategory", "source"]
ENRICH_FIELDS = BASE_FIELDS + ["recurring_label", "recurring_cadence",
                               "recurring_monthly_cost", "recurring_status",
                               "spend_type"]
EVERYDAY_CATEGORIES = {"groceries", "restaurants", "coffee", "gas", "fast food"}
TRANSFER_WORDS = ("transfer", "payment", "card payment", "ach pmt", "autopay payment")
BNPL_WORDS = ("affirm", "klarna", "afterpay", "pay in 4", "pay-in-4")


def repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def norm(s):
    return (s or "").strip().lower()


def money(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def read_csv(path):
    if not path or not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields=ENRICH_FIELDS):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def default_config_path(filename):
    return os.path.join(repo_root(), "assets", filename)


def parse_date(value):
    return datetime.date.fromisoformat(str(value)[:10])


def month_key(value):
    d = parse_date(value)
    return "%04d-%02d" % (d.year, d.month)


def merchant_key(desc):
    s = norm(desc)
    s = re.split(r"des:|conf|indn:|id:", s)[0]
    s = re.sub(r"[^a-z0-9&' ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return " ".join(s.split()[:3]) or "unknown"


def load_rules(path):
    rules = []
    for row in read_csv(path):
        match = norm(row.get("match"))
        if not match:
            continue
        rules.append(row | {"_match": match})
    return rules


def apply_account_aliases(row, aliases):
    text = " ".join([row.get("account", ""), row.get("institution", ""),
                     row.get("description", "")]).lower()
    for rule in aliases:
        if rule["_match"] in text:
            if row.get("account"):
                row["account"] = rule.get("account") or row.get("account", "")
            else:
                row["account"] = rule.get("account") or ""
            row["institution"] = rule.get("institution") or row.get("institution", "")
            return


def apply_category_rules(row, rules):
    if money(row.get("amount")) >= 0:
        return
    desc = norm(row.get("description"))
    for rule in rules:
        if rule["_match"] in desc:
            row["category"] = rule.get("category") or row.get("category", "")
            sub = rule.get("subcategory")
            if sub:
                row["subcategory"] = sub
            elif not row.get("subcategory"):
                row["subcategory"] = "Needs Review"
            return


def spend_type(row):
    desc = norm(row.get("description"))
    category = norm(row.get("category"))
    if any(w in desc for w in TRANSFER_WORDS) or category in {"transfer", "transfers"}:
        return "transfer"
    if any(w in desc for w in BNPL_WORDS):
        return "bnpl"
    return "spend" if money(row.get("amount")) < 0 else "income"


def cadence_from_gap(days):
    if 24 <= days <= 38:
        return "monthly", days
    if 80 <= days <= 100:
        return "quarterly", days
    if 330 <= days <= 400:
        return "annual", days
    return "irregular", days


def expected_lapse_days(cadence, median_gap):
    if cadence == "monthly":
        return 60
    if cadence == "quarterly":
        return 150
    if cadence == "annual":
        return 450
    return max(60, int(median_gap * 2))


def label_for(desc, labels):
    d = norm(desc)
    for rule in labels:
        if rule["_match"] in d:
            return rule.get("label") or desc, rule.get("category") or ""
    return "", ""


def detect_recurring(rows, labels=None, today=None):
    labels = labels or []
    today = today or max((parse_date(r["date"]) for r in rows), default=datetime.date.today())
    groups = {}
    for row in rows:
        amt = money(row.get("amount"))
        if amt >= 0:
            continue
        if row.get("spend_type") in {"transfer", "bnpl"}:
            continue
        category = norm(row.get("category"))
        if category in EVERYDAY_CATEGORIES:
            continue
        groups.setdefault(merchant_key(row.get("description")), []).append(row)

    recurring = []
    for key, items in groups.items():
        items = sorted(items, key=lambda r: r["date"])
        if len(items) < 3:
            continue
        months = {month_key(r["date"]) for r in items}
        if len(months) < 3:
            continue
        amounts = [abs(money(r["amount"])) for r in items]
        median_amount = statistics.median(amounts)
        if median_amount <= 0:
            continue
        near = [a for a in amounts if abs(a - median_amount) / median_amount <= 0.15]
        if len(near) <= len(amounts) / 2:
            continue
        dates = [parse_date(r["date"]) for r in items]
        gaps = [(b - a).days for a, b in zip(dates, dates[1:]) if (b - a).days > 0]
        if not gaps:
            continue
        median_gap = statistics.median(gaps)
        if median_gap < 11:
            continue
        cadence, gap = cadence_from_gap(median_gap)
        monthly_cost = median_amount * 30.44 / gap
        if monthly_cost < 2:
            continue
        label, label_category = label_for(items[-1].get("description", ""), labels)
        if not label:
            label = items[-1].get("description") or key.title()
        last_seen = dates[-1]
        status = "possibly_cancelled" if (today - last_seen).days > expected_lapse_days(cadence, gap) else "active"
        recurring.append({
            "key": key,
            "label": label,
            "category": label_category or items[-1].get("category", ""),
            "cadence": cadence,
            "median_gap_days": round(gap, 1),
            "median_amount": round(median_amount, 2),
            "monthly_cost": round(monthly_cost, 2),
            "first_seen": dates[0].isoformat(),
            "last_seen": last_seen.isoformat(),
            "charge_count": len(items),
            "status": status,
        })
    recurring.sort(key=lambda r: (-r["monthly_cost"], r["label"].lower()))
    return recurring


def load_manual_balances(path):
    balances = []
    for row in read_csv(path):
        account = row.get("account") or ""
        if not account:
            continue
        typ = norm(row.get("type")) or "cash"
        if typ not in {"cash", "investment", "credit", "loan"}:
            typ = "cash"
        balances.append({
            "account": account,
            "balance": round(money(row.get("balance")), 2),
            "type": typ,
            "note": row.get("note", ""),
        })
    return balances


def enrich_rows(rows, category_rules=None, aliases=None, labels=None, today=None):
    category_rules = category_rules or []
    aliases = aliases or []
    labels = labels or []
    out = []
    for raw in rows:
        row = {field: raw.get(field, "") for field in BASE_FIELDS}
        row["amount"] = round(money(row.get("amount")), 2)
        apply_account_aliases(row, aliases)
        apply_category_rules(row, category_rules)
        row["spend_type"] = spend_type(row)
        row["recurring_label"] = ""
        row["recurring_cadence"] = ""
        row["recurring_monthly_cost"] = ""
        row["recurring_status"] = ""
        out.append(row)

    recurring = detect_recurring(out, labels, today=today)
    recurring_by_key = {r["key"]: r for r in recurring}
    for row in out:
        rec = recurring_by_key.get(merchant_key(row.get("description")))
        if not rec:
            continue
        row["recurring_label"] = rec["label"]
        row["recurring_cadence"] = rec["cadence"]
        row["recurring_monthly_cost"] = "%.2f" % rec["monthly_cost"]
        row["recurring_status"] = rec["status"]
    return out, recurring


def summarize_accounts(rows, manual_balances):
    latest_by_account = {}
    for row in rows:
        account = row.get("account") or "Unspecified"
        latest_by_account.setdefault(account, {
            "account": account,
            "institution": row.get("institution", ""),
            "type": "cash",
            "balance": 0.0,
            "transaction_count": 0,
        })
        latest_by_account[account]["transaction_count"] += 1
    for bal in manual_balances:
        latest_by_account[bal["account"]] = {
            "account": bal["account"],
            "institution": "",
            "type": bal["type"],
            "balance": bal["balance"],
            "transaction_count": latest_by_account.get(bal["account"], {}).get("transaction_count", 0),
        }
    accounts = sorted(latest_by_account.values(), key=lambda r: (r["type"], r["account"].lower()))
    assets = sum(a["balance"] for a in accounts if a["type"] in {"cash", "investment"})
    liabilities = sum(a["balance"] for a in accounts if a["type"] in {"credit", "loan"})
    return accounts, {
        "assets": round(assets, 2),
        "liabilities": round(liabilities, 2),
        "netWorth": round(assets + liabilities, 2),
    }


def enrich_file(input_path, output_path, category_path, aliases_path, labels_path,
                balances_path, meta_path=None, today=None):
    rows = read_csv(input_path)
    enriched, recurring = enrich_rows(
        rows,
        category_rules=load_rules(category_path),
        aliases=load_rules(aliases_path),
        labels=load_rules(labels_path),
        today=today,
    )
    balances = load_manual_balances(balances_path)
    accounts, net_worth = summarize_accounts(enriched, balances)
    write_csv(output_path, enriched)
    meta = {"recurring": recurring, "manualBalances": balances,
            "accounts": accounts, "netWorth": net_worth}
    if meta_path:
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, sort_keys=True)
    return enriched, meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="input", required=True, help="deduped master CSV")
    ap.add_argument("--out", default="enriched_transactions.csv")
    ap.add_argument("--meta", default="finance-enrichment.json")
    ap.add_argument("--categories", default=default_config_path("merchant_categories.example.csv"))
    ap.add_argument("--aliases", default=default_config_path("account_aliases.example.csv"))
    ap.add_argument("--labels", default=default_config_path("recurring_labels.example.csv"))
    ap.add_argument("--balances", default=default_config_path("manual_balances.example.csv"))
    args = ap.parse_args()
    rows, meta = enrich_file(args.input, args.out, args.categories, args.aliases,
                             args.labels, args.balances, meta_path=args.meta)
    print("WROTE %s (%d rows)" % (args.out, len(rows)))
    print("WROTE %s (%d recurring, %d accounts)" %
          (args.meta, len(meta["recurring"]), len(meta["accounts"])))


if __name__ == "__main__":
    main()
