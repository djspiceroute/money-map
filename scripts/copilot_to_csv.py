#!/usr/bin/env python3
"""
copilot_to_csv.py - convert copilot-money-cli JSON output into a canonical CSV.

Copilot Money has no official API, but the community CLI can pull your data:
    https://github.com/JaviSoto/copilot-money-cli  (binary: `copilot`)

    copilot transactions list --all --output json > copilot_dump.json
    python copilot_to_csv.py copilot_dump.json --out copilot_canonical.csv

This is an UNOFFICIAL tool ("vibe-coded", per its author) that talks to Copilot's
private web API and may break or violate Copilot's Terms of Service - use at your
own risk, and treat the exact JSON shape as unstable. This converter is therefore
deliberately defensive: it accepts a top-level list, or an object with a
`transactions` / `data` / `items` array, and pulls fields by trying several
likely key names.

SIGN: Copilot generally reports expenses as negative and income as positive,
matching this pipeline's convention, so amounts are kept as-is by default. VERIFY
on first run (purchases should be negative); if they're flipped, re-run with
`--invert`.
"""
import argparse, csv, json

FIELDS = ["date", "description", "amount", "account", "institution", "category", "subcategory", "source"]


def _first(d, *keys):
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, ""):
            return d[k]
    return None


def _name(v):
    """A field might be a string or a nested object like {'name': 'Groceries'}."""
    if isinstance(v, dict):
        return _first(v, "name", "displayName", "title") or ""
    return v if v is None else str(v)


def _num(v):
    if isinstance(v, dict):
        v = _first(v, "amount", "value")
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--out", default="copilot_canonical.csv")
    ap.add_argument("--invert", action="store_true",
                    help="flip amount sign (use if purchases come out positive)")
    args = ap.parse_args()

    data = json.load(open(args.dump))
    if isinstance(data, dict):
        txns = _first(data, "transactions", "data", "items", "results") or []
    else:
        txns = data
    mult = -1 if args.invert else 1

    rows = []
    for t in txns:
        if not isinstance(t, dict):
            continue
        amt = _num(_first(t, "amount"))
        date = _first(t, "date", "transactionDate", "postedDate")
        if amt is None or not date:
            continue
        cat = _name(_first(t, "category")) or ""
        sub = _name(_first(t, "subcategory", "subCategory")) or ""
        if not sub and " > " in cat:
            parts = [p.strip() for p in cat.split(">") if p.strip()]
            cat = parts[0] if parts else cat
            sub = " / ".join(parts[1:])
        rows.append({
            "date": str(date)[:10],
            "description": _name(_first(t, "name", "merchant", "description")) or "",
            "amount": round(amt * mult, 2),
            "account": _name(_first(t, "account", "accountName")) or "",
            "institution": _name(_first(t, "institution")) or "",
            "category": cat,
            "subcategory": sub,
            "source": "copilot",
        })
    rows.sort(key=lambda r: r["date"])
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print("WROTE %s (%d transactions)" % (args.out, len(rows)))
    print("VERIFY: open a few rows - purchases should be NEGATIVE. If flipped, re-run with --invert.")


if __name__ == "__main__":
    main()
