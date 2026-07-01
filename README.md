# money-map

**Turn messy financial exports from every bank and app into one clean, de-duplicated, categorized dataset — and a private local dashboard.**

money-map is a [Claude](https://claude.ai) **skill** plus a set of small, dependency-free Python scripts. Point it at a folder of CSV exports (or a live Plaid connection) and it normalizes wildly different formats into one canonical schema, conservatively merges and de-duplicates overlapping sources, categorizes spending with editable rules, detects recurring subscriptions and bills, and builds a self-contained HTML dashboard with spending, net-worth, debt, and trend insights.

> 🔒 **Everything runs locally.** No data is uploaded anywhere. The scripts are Python-stdlib-only, and the dashboard is a single offline HTML file. Your financial data never leaves your machine.

---

## Why

Financial data is scattered across banks, credit cards, and finance apps — each exporting a different CSV shape, with different column names, date formats, and **sign conventions** (some use negative for spending, some positive, some split debit/credit into two columns). Stitching them together by hand is tedious and error-prone, and naively merging two sources double-counts every overlapping transaction. money-map handles the plumbing so you get one trustworthy ledger and a dashboard you can actually reason about.

## What you get

- **One canonical dataset** from many sources (built-in adapters for Apple Card, Copilot, Mint, Monarch, YNAB, Plaid, and two generic bank formats — adding a new bank is a single dict).
- **Conservative de-duplication** that *flags* rather than deletes, separating high-confidence exact duplicates from cross-source matches that might really be transfer legs.
- **Editable, code-free enrichment** — category rules, account aliases, and friendly recurring labels all live in small CSVs you can correct and rebuild.
- **Automatic recurring/subscription detection** from amount-repetition over time (catches subs no rule knows about, and flags "possibly cancelled" ones).
- **A private dashboard** — Overview, Net Worth, Spending, Recurring/Subscriptions, Accounts, Debt & Bills, Transactions, and multi-year Analytics.

## How it works

```
  exports / pulls  ->  NORMALIZE  ->  MERGE + DEDUPE  ->  CATEGORIZE/ENRICH  ->  DASHBOARD
  (any format)         (one schema)   (flag duplicates)   (rules + detection)    (insights)
```

Canonical schema (one row per transaction):

```
date, description, amount (negative = money out), account, institution, category, subcategory, source
```

## Quickstart (try it on the bundled sample data)

The repo ships with synthetic sample exports so you can see the pipeline run end-to-end in seconds. Requires Python 3 (stdlib only — nothing to install).

```bash
cd scripts

# 1. See which adapter each file matches (no output written)
python3 ingest.py --in ../assets/sample_data --inspect

# 2. Normalize every export into one canonical CSV
python3 ingest.py --in ../assets/sample_data --out canonical_transactions.csv

# 3. Audit for duplicates (flags, never deletes)
python3 dedup.py --in canonical_transactions.csv --audit-only
```

You'll see the Apple Card and generic-bank formats auto-detected, purchases normalized to negative amounts, and the cross-source duplicate (a Whole Foods charge appearing on two accounts) flagged for review. To build the master file after reviewing the audit:

```bash
python3 dedup.py --in canonical_transactions.csv --out master_transactions.csv --apply
```

> The sample data is entirely fictional (`ACME CORP`, `Example Bank`, fake store numbers). Replace `../assets/sample_data` with a folder of your own exports to use it for real.

## Using it with Claude (the intended way)

money-map is designed to be driven by Claude for a **non-technical user** — you just drop exports in a folder and say *"import my transactions"* or *"build me a finance dashboard,"* and Claude runs the pipeline, makes sensible defaults, and asks short plain-language questions only when something needs your judgment.

Install it as a personal skill:

```bash
# Claude Code
git clone https://github.com/djspiceroute/money-map.git ~/.claude/skills/money-map
```

In the **Claude desktop app**, add it via the app's skill/import mechanism (point it at this repo or the cloned folder). Once installed, the skill activates automatically when you ask about importing transactions, combining statements, tracking net worth, finding subscriptions, or building a budgeting/finance dashboard. See [`SKILL.md`](SKILL.md) for the full instructions Claude follows.

## Supported sources

| Source | How you export it |
|---|---|
| **Apple Card** | card.apple.com → Card Balance → Statements → Export Transactions (CSV) |
| **Copilot Money** | Settings → Export Data (CSV), or pull live via the community CLI |
| **Mint / Monarch / YNAB** | each app's Transactions → Export CSV |
| **Plaid** (live balances, liabilities, transactions) | official Plaid CLI → `plaid_to_csv.py` — see [`references/plaid-setup.md`](references/plaid-setup.md) |
| **Any bank** | a plain CSV (single Amount column, or split Debit/Credit) auto-detects |

Adding a bank or app that isn't recognized is one dict in [`scripts/adapters.py`](scripts/adapters.py) — see [`references/source-adapters.md`](references/source-adapters.md).

## Configuration (all code-free, editable CSVs)

Correct any mistake by editing a CSV and rebuilding — never a code change. Templates are in [`assets/`](assets/):

| File | Purpose |
|---|---|
| `merchant_categories.example.csv` | substring → category rules (applied to spending only) |
| `account_aliases.example.csv` | merge generic labels like `CREDIT CARD` into real account names |
| `recurring_labels.example.csv` | rename cryptic bank descriptors to friendly names |
| `manual_balances.example.csv` | add any account (investments, mortgage, property) to net worth |
| `sources.example.json` | pin adapters/accounts when auto-detection needs help |

See [`references/enrichment.md`](references/enrichment.md) for the full method.

## Repository layout

```
money-map/
├── SKILL.md                 # the skill Claude follows (start here)
├── references/              # deep-dive docs, loaded on demand
│   ├── source-adapters.md   # canonical schema + adding new sources
│   ├── enrichment.md        # categories, aliases, recurring detection, net worth
│   ├── dashboard.md         # dashboard screens + build architecture
│   ├── plaid-setup.md       # optional live bank connection via Plaid
│   └── refresh.md           # keeping the data current
├── scripts/                 # dependency-free Python (stdlib only)
│   ├── ingest.py            # normalize a folder of exports → canonical CSV
│   ├── adapters.py          # source adapters + auto-detection
│   ├── dedup.py             # conservative merge + duplicate audit
│   ├── plaid_to_csv.py      # Plaid JSON dump → canonical CSV
│   └── copilot_to_csv.py    # Copilot CLI JSON → canonical CSV
└── assets/                  # editable config templates + synthetic sample data
```

## Privacy

- **Local-only.** Scripts use the Python standard library only; the dashboard is one offline HTML file. Nothing is sent over the network (Plaid, if you opt in, runs via the official CLI on your machine).
- **The repo contains no real data** — only synthetic samples and `.example` config templates.
- **The [`.gitignore`](.gitignore) blocks real data by default.** All `*.csv`/`*.json` are ignored except the bundled examples, so if you run the pipeline inside a clone, your own exports and generated dashboards won't be committed. Don't put real exports in `assets/`.

## Contributing

Adapters for more banks/apps are the most useful contributions — most are a single dict in `scripts/adapters.py` plus a note in `references/source-adapters.md`. Please keep the scripts dependency-free (stdlib only) and never commit real financial data.

## License

[MIT](LICENSE) — © 2026 djspiceroute.

*Not affiliated with Plaid, Copilot Money, Apple, Mint, Monarch, or YNAB. This is a personal-use tool, not financial advice.*
