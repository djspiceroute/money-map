#!/usr/bin/env python3
"""
dedup.py - merge canonical CSVs, flag duplicates conservatively, write a report.

Why this is its own step: when you combine a long-history app export (the
"backbone") with a live bank/Plaid pull (the "top-up"), the same transaction
often appears twice - once per source, sometimes under slightly different
account labels. Aggressively deleting rows risks losing real transactions
(two identical coffees on one day ARE two transactions). So the default here is
FLAG, not delete. You decide what to remove.

Usage:
    # Merge several canonical files and write a deduped master + audit report.
    python dedup.py --in canonical_transactions.csv more.csv --out master.csv

    # Only audit (write the report, do NOT drop anything):
    python dedup.py --in canonical_transactions.csv --audit-only

Duplicate tiers (highest confidence first):
    EXACT  - same date, same amount, same merchant, SAME account  -> almost
             certainly a true duplicate; --apply removes all but one.
    CROSS  - same date, same amount, same merchant, DIFFERENT account/source
             -> usually a cross-source dupe, but sometimes two legitimate legs
             of a transfer. Flagged for review; never auto-removed.
"""
import argparse, csv, re, datetime

FIELDS = ["date", "description", "amount", "account", "institution", "category", "subcategory", "source"]


def norm_merchant(d):
    s = (d or "").lower()
    s = re.split(r"des:|conf|indn:|id:", s)[0]
    s = re.sub(r"[^a-z&' ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return " ".join(s.split()[:2])


def load(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def key(r):
    amt = round(abs(float(r["amount"])) * 100)
    return (r["date"], amt, norm_merchant(r["description"]))


def fmt(n):
    return "$%s" % format(abs(float(n)), ",.2f")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inputs", nargs="+", required=True)
    ap.add_argument("--out", default="master_transactions.csv")
    ap.add_argument("--report", default="Duplicate Audit.md")
    ap.add_argument("--audit-only", action="store_true",
                    help="write the report but do not write a deduped master")
    ap.add_argument("--apply", action="store_true",
                    help="actually remove EXACT same-account duplicates (keep one)")
    args = ap.parse_args()

    rows = []
    for p in args.inputs:
        rows.extend(load(p))
    for r in rows:
        r["amount"] = float(r["amount"])

    groups = {}
    for r in rows:
        if r["amount"] >= 0:
            continue  # only audit outflows; income rarely duplicates cleanly
        groups.setdefault(key(r), []).append(r)

    exact, cross = [], []
    for g in groups.values():
        if len(g) < 2:
            continue
        accts = {x["account"] for x in g}
        (exact if len(accts) == 1 else cross).append(g)

    imp_exact = sum((len(g) - 1) * abs(g[0]["amount"]) for g in exact)
    imp_cross = sum((len(g) - 1) * abs(g[0]["amount"]) for g in cross)
    exact.sort(key=lambda g: -abs(g[0]["amount"]))
    cross.sort(key=lambda g: -abs(g[0]["amount"]))

    md = ["# Duplicate Transaction Audit", ""]
    md.append("Generated %s . %d rows scanned\n" % (datetime.date.today().isoformat(), len(rows)))
    md.append("## Summary\n")
    md.append("- **EXACT (same date, amount, merchant AND account):** %d groups . ~%s. Highest confidence true duplicates.\n" % (len(exact), fmt(imp_exact)))
    md.append("- **CROSS (same date, amount, merchant, DIFFERENT account):** %d groups . ~%s. Review - some are transfer legs, not dupes.\n" % (len(cross), fmt(imp_cross)))

    def block(title, arr, n=30):
        md.append("\n## %s\n" % title)
        if not arr:
            md.append("_None found._\n")
            return
        for g in arr[:n]:
            md.append("- **%s . %s . %s** x%d" % (g[0]["date"], fmt(g[0]["amount"]), g[0]["description"][:40], len(g)))
            for x in g:
                md.append("    - %s . %s . %s . %s . %s" % (x["date"], fmt(x["amount"]), x["account"] or "?", x["source"], x["category"] or "-"))
        if len(arr) > n:
            md.append("\n_...and %d more groups._" % (len(arr) - n))

    block("CROSS - review these first", cross)
    block("EXACT - same account", exact)
    open(args.report, "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("exact:%d (~%s)  cross:%d (~%s)  -> %s" % (len(exact), fmt(imp_exact), len(cross), fmt(imp_cross), args.report))

    if args.audit_only:
        return

    drop = set()
    if args.apply:
        for g in exact:
            for x in g[1:]:
                drop.add(id(x))
    kept = [r for r in rows if id(r) not in drop]
    kept.sort(key=lambda r: r["date"])
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in kept:
            w.writerow(r)
    print("WROTE %s (%d rows%s)" % (args.out, len(kept),
          ", removed %d exact dupes" % len(drop) if args.apply else "; no rows removed - pass --apply to drop EXACT dupes"))


if __name__ == "__main__":
    main()
