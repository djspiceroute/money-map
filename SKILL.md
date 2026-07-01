---
name: money-map
description: >-
  Ingest personal financial data from many sources - bank/credit-card CSV
  exports, finance-app exports (Copilot, Mint, Monarch, YNAB), Apple Card
  exports, and Plaid pulls - into one clean, de-duplicated, categorized
  transaction dataset, then turn it into a private local dashboard with
  spending, net-worth, recurring/subscription, debt, and trend insights. Use
  this skill whenever someone wants to combine statements or app exports,
  "import my transactions", build a personal finance or budgeting dashboard,
  track net worth, find subscriptions/recurring charges, de-duplicate merged
  statements, categorize spending, or analyze where their money goes - even if
  they only mention one CSV or don't say the word "dashboard". The user is
  typically non-technical and just provides exports; you do the plumbing.
---

# money-map — personal finance ingestion & dashboard

Turn messy, heterogeneous financial exports into one trustworthy dataset and a
private dashboard. Everything runs locally on the user's machine - no data is
uploaded anywhere.

The user is usually **non-technical**. They will mostly drop CSV files in a
folder (and optionally set up a live bank connection). Your job is to run the
pipeline, make sensible decisions, and ask short, plain-language questions only
when something genuinely needs their judgment (e.g. "is this $40 charge on two
cards one purchase or two?").

## The pipeline at a glance

```
  exports/pulls  ->  NORMALIZE  ->  MERGE + DEDUPE  ->  CATEGORIZE/ENRICH  ->  DASHBOARD
  (any format)      (one schema)   (flag duplicates)   (rules + detection)    (insights)
```

Five stages. Stages 1–2 ship as ready-to-run scripts in `scripts/`; stages 3–5
provide the method, config templates, and reference docs for the agent (or you)
to carry out — there is no fixed script for them yet:

1. **Normalize** every input to one canonical schema (`ingest.py` + `adapters.py`).
2. **Merge & de-duplicate** the sources conservatively (`dedup.py`).
3. **Categorize & enrich** - apply category rules, detect recurring charges,
   normalize account names (see `references/enrichment.md`).
4. **Build the dashboard** from the clean dataset (see `references/dashboard.md`).
5. **Refresh** on a cadence (see `references/refresh.md`).

Read the linked reference file when you reach each stage; this file stays short
on purpose.

## Stage 1 - Normalize (the key idea: source adapters)

The hard part of financial data is that every exporter uses different column
names, date formats, and **sign conventions** (some use negative for spending,
some positive, some split debit/credit columns). The skill solves this with
**adapters**: a small description of how one source's columns map onto the
canonical schema. Auto-detection picks the right adapter from the file's
headers; you rarely need to specify it.

Canonical schema (one row per transaction):
`date, description, amount (negative = money out), account, institution, category, subcategory, source`

To ingest a folder of exports:

```bash
cd scripts
python ingest.py --in <folder-of-exports> --out canonical_transactions.csv
```

First run `--inspect` to show which adapter each file matched, so you can catch a
misread before producing output:

```bash
python ingest.py --in <folder-of-exports> --inspect
```

Built-in adapters: Apple Card, Copilot, Mint, Monarch, YNAB, Plaid, plus two
generic bank formats (single Amount column, or split Debit/Credit). Adding a new
bank/app is one dict in `adapters.py` - see `references/source-adapters.md`.

For a **live bank connection** via Plaid, see `references/plaid-setup.md`. Convert
a Plaid JSON dump with `python plaid_to_csv.py dump.json --out plaid_canonical.csv`.
Apple Card cannot connect to Plaid; the user exports its CSV from card.apple.com.

**Always sanity-check the sign** after the first ingest: open a few rows and
confirm purchases are negative and paychecks/refunds positive. A flipped sign is
the single most common ingestion error.

## Stage 2 - Merge & de-duplicate

When a long-history app export (the "backbone") is combined with a live
bank/Plaid pull (the "top-up"), the same transaction often appears twice -
sometimes under slightly different account labels. Deleting aggressively is
dangerous: two identical coffees on one day really are two transactions. So the
default is **flag, don't delete**.

```bash
python dedup.py --in canonical_transactions.csv plaid_canonical.csv --audit-only
```

This writes `Duplicate Audit.md` grouping suspected duplicates into:

- **EXACT** - same date, amount, merchant AND same account. Almost always true
  duplicates; safe to remove all-but-one with `--apply`.
- **CROSS** - same date, amount, merchant but DIFFERENT account/source. Usually a
  cross-source dupe, but sometimes the two legs of a transfer. Show these to the
  user before removing anything.

Only after the user reviews the audit, produce the master file:

```bash
python dedup.py --in canonical_transactions.csv plaid_canonical.csv \
    --out master_transactions.csv --apply        # removes EXACT dupes, keeps one
```

## Stage 3 - Categorize & enrich

Make the dataset meaningful and tunable without code. All of this is driven by
small editable CSVs so the user can correct mistakes and rebuild. See
`references/enrichment.md` for the full method; the essentials:

- **Category rules** (`merchant_categories.csv`: match, category) - substring ->
  category, applied to **outflows only** so a merchant rule never accidentally
  recategorizes income. Order matters (put specific rules before general).
- **Account aliases** (`account_aliases.csv`) - merge generic labels like
  "CREDIT CARD" into real names and group them under an institution.
- **Recurring detection** - automatically find subscriptions and bills by
  amount-repetition over time (see the method in `references/enrichment.md`):
  a merchant is "recurring" when it has enough charges, in enough separate
  months, clustered around a stable amount, at a regular cadence. Cadence
  (monthly/quarterly/annual) is inferred from the median gap between charges.
  Charges that stop for longer than expected are flagged as "possibly cancelled".
- **Recurring labels** (`recurring_labels.csv`: match, label, category) - rename
  cryptic bank descriptors to friendly names.

## Stage 4 - Build the dashboard

The clean dataset powers a single self-contained HTML dashboard (opens in any
browser, no server, no internet). See `references/dashboard.md` for the build and
the full list of screens and the insight each one provides - Overview, Net
Worth, Spending (category treemap, calendar heatmap, merchants, income
sources), Recurring/Subscriptions, Accounts, Debt & payoff simulators,
Transactions, and multi-year Analytics/Insights.

## Stage 5 - Refresh

Personal finance data is never "done". See `references/refresh.md` for a simple
monthly/weekly routine: re-export or re-pull, re-run ingest -> dedup -> build.

## How to run this for a non-technical user

1. Ask them to put all their exports in one folder (and help them export from
   each app/bank - `references/source-adapters.md` lists where each export lives).
2. Run `ingest.py --inspect`, then `ingest.py` to normalize. Confirm signs.
3. Run `dedup.py --audit-only`, summarize the audit in plain language, and ask
   about anything in the CROSS list before applying.
4. Set up category/alias CSVs with sensible defaults; invite them to correct any
   miscategorized merchants, then rebuild.
5. Build the dashboard and walk them through what each screen tells them.

Keep questions short and concrete, default to safe choices, and never delete
their data without confirmation.
