#!/usr/bin/env python3
"""
ingest.py - turn a folder of financial exports into one canonical CSV.

Usage:
    # Auto mode: point it at a folder of CSVs, it detects each format.
    python ingest.py --in ./inbox --out canonical_transactions.csv

    # Inspect mode: just report what adapter each file would use (no output).
    python ingest.py --in ./inbox --inspect

    # Config mode: use a sources.json to pin adapters / accounts explicitly.
    python ingest.py --config sources.json --out canonical_transactions.csv

sources.json (optional, for when auto-detection needs help) looks like:
{
  "sources": [
    {"file": "inbox/applecard.csv", "adapter": "apple_card"},
    {"file": "inbox/chase_checking.csv", "adapter": "generic_amount",
     "account": "Chase Checking", "institution": "Chase"},
    {"file": "inbox/copilot_full.csv", "adapter": "copilot"}
  ]
}

This is dependency-free (stdlib only). It never deletes input files; it only
writes the canonical output. Run dedup.py afterwards to merge/flag duplicates.
"""
import argparse, csv, json, os, sys
import adapters as AD


def gather_files(folder):
    out = []
    for root, _dirs, files in os.walk(folder):
        for fn in files:
            if fn.lower().endswith((".csv", ".tsv", ".txt")):
                out.append(os.path.join(root, fn))
    return sorted(out)


def process_file(path, adapter_id=None, account=None, institution=None, label=None):
    headers, rows = AD.read_csv(path)
    if not headers:
        return None, [], "empty or unreadable"
    aid = adapter_id or AD.detect_adapter(headers)
    if not aid:
        return None, [], "could not detect format (headers: %s)" % ", ".join(headers[:8])
    canon = AD.apply_adapter(headers, rows, aid,
                             source_label=label or os.path.splitext(os.path.basename(path))[0],
                             account_override=account, institution_override=institution)
    return aid, canon, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inbox", help="folder of export files to ingest")
    ap.add_argument("--config", help="sources.json with explicit per-file adapters")
    ap.add_argument("--out", default="canonical_transactions.csv")
    ap.add_argument("--inspect", action="store_true", help="report detection only, write nothing")
    args = ap.parse_args()

    jobs = []  # (path, adapter_id_or_None, account, institution, label)
    if args.config:
        cfg = json.load(open(args.config))
        for s in cfg.get("sources", []):
            jobs.append((s["file"], s.get("adapter"), s.get("account"),
                         s.get("institution"), s.get("label")))
    elif args.inbox:
        for p in gather_files(args.inbox):
            jobs.append((p, None, None, None, None))
    else:
        print("Provide --in <folder> or --config <sources.json>", file=sys.stderr)
        sys.exit(2)

    all_rows, report = [], []
    for path, aid, acct, inst, label in jobs:
        if not os.path.exists(path):
            report.append((path, "MISSING", 0))
            continue
        used, canon, err = process_file(path, aid, acct, inst, label)
        if err:
            report.append((path, "SKIP: " + err, 0))
            continue
        report.append((path, used, len(canon)))
        all_rows.extend(canon)

    print("\n%-45s %-22s %s" % ("FILE", "ADAPTER", "ROWS"))
    print("-" * 80)
    for path, used, n in report:
        print("%-45s %-22s %d" % (os.path.basename(path)[:44], used, n))
    print("-" * 80)
    print("TOTAL canonical rows: %d" % len(all_rows))

    if args.inspect:
        print("\n(inspect mode - nothing written)")
        return

    all_rows.sort(key=lambda r: r["date"])
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=AD.CANON_FIELDS)
        w.writeheader()
        w.writerows(all_rows)
    print("\nWROTE %s (%d rows)" % (args.out, len(all_rows)))
    print("Next: review sign conventions on a few rows, then run dedup.py.")


if __name__ == "__main__":
    main()
