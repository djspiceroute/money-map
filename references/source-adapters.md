# Source adapters & the canonical schema

## Canonical schema

Every input becomes rows of:

| field | meaning |
|---|---|
| `date` | `YYYY-MM-DD` |
| `description` | merchant / memo |
| `amount` | **signed**: negative = money out (spend), positive = money in |
| `account` | account or card name |
| `institution` | bank / provider |
| `category` | top-level category (may be blank) |
| `subcategory` | finer category (may be blank; e.g. Restaurants under Food) |
| `source` | which input the row came from |

Many exporters put a hierarchy in one field like `Food and Drink > Restaurants >
Fast Food`. The adapter splits that automatically: the first level becomes
`category` and the rest becomes `subcategory`. Sources with a separate
subcategory/"detailed category" column are mapped directly.

The sign convention is the contract the whole pipeline depends on. If a source
uses the opposite convention, its adapter inverts it on import.

## What an adapter is

An adapter is a small dict in `scripts/adapters.py` describing how one source's
columns map onto the schema, including how to derive a signed amount. Three
amount "modes" cover almost every exporter:

- **Single amount column** - one `amount` column. `sign: as_is` if negative
  already means spend, `sign: invert` if positive means spend.
- **Two columns** - separate Debit/Credit or Outflow/Inflow columns
  (`sign: abs_by_type`). Out becomes negative, in positive.
- **Type column** - one amount plus a "Transaction Type" column whose value
  (debit/credit) decides the sign (`sign: abs_by_type` with `type_debit_values`).

Auto-detection matches a file's headers against each adapter's `signature`
(required header substrings) and picks the most specific match. Header name
variants (e.g. "Posting Date" -> date) are handled by the `ALIASES` table.

## Built-in adapters and where each export comes from

| adapter | source | where the user exports it |
|---|---|---|
| `apple_card` | Apple Card | card.apple.com -> Card Balance -> Statements -> Export Transactions (CSV). Positive = purchase, so it is inverted. |
| `copilot` | Copilot Money (iOS) | Settings -> Export Data (CSV). Or pull it live via CLI - see below. |
| `mint` | Mint / Intuit | Transactions -> Export (CSV). Uses a Transaction Type column for sign. |
| `monarch` | Monarch Money | Transactions -> Export CSV. |
| `ynab` | YNAB | Account -> Export -> register CSV. Has Outflow/Inflow columns. |
| `plaid` | Plaid CLI | produced by `plaid_to_csv.py`; see `plaid-setup.md`. |
| `generic_amount` | any bank | a plain CSV with Date / Description / Amount. |
| `generic_debit_credit` | any bank | a CSV with Date / Description / Debit / Credit. |

Most US banks export a "generic" format and will auto-detect. If a bank export
is unusual, see "Adding a new source" below.

## Adding a new source (one dict, no other code)

If a bank or app isn't recognized, add an entry to `ADAPTERS` in
`scripts/adapters.py`. Example for a bank that exports
`Posted Date, Payee, Withdrawal, Deposit, Running Balance`:

```python
"my_bank": {
    "label": "My Bank checking export",
    "signature": ["posted date", "withdrawal", "deposit"],
    "date": "Posted Date", "desc": "Payee",
    "debit": "Withdrawal", "credit": "Deposit", "sign": "abs_by_type",
    "account_fixed": "My Bank Checking", "institution_fixed": "My Bank",
},
```

Then re-run `ingest.py --inspect` to confirm it matches. If the export is for a
single account, set `account_fixed`/`institution_fixed`; if the file contains
multiple accounts in a column, set `account`/`institution` to those column names
instead.

## Pulling Copilot Money live via CLI (optional)

Copilot has no official API, but an **unofficial** community CLI can pull your
data so you don't have to export a CSV each time:
https://github.com/JaviSoto/copilot-money-cli (binary `copilot`).

```bash
brew install JaviSoto/tap/copilot-money-cli     # or: cargo install copilot-money-cli
copilot auth login                              # browser or email-link / paste token
copilot transactions list --all --output json > copilot_dump.json
python scripts/copilot_to_csv.py copilot_dump.json --out copilot_canonical.csv
```

Then feed `copilot_canonical.csv` into `dedup.py` alongside your other sources.

Caveats to relay to the user: it's **unofficial** (self-described as "vibe-coded"),
talks to Copilot's private web API, may break at any time, and its use may be
restricted by Copilot's Terms of Service. The JSON shape can change, so
`copilot_to_csv.py` reads fields defensively; **verify the amount sign on the
first run** (purchases should be negative; re-run with `--invert` if not). It's
read-only by default. Prefer this only if the user is comfortable with those
trade-offs; the plain **Settings -> Export Data** CSV (the `copilot` adapter) is
the safe default.

## Pinning adapters with a config (optional)

When auto-detection needs help (e.g. two files share a generic format but are
different accounts), use a `sources.json` and run `ingest.py --config`:

```json
{
  "sources": [
    {"file": "inbox/applecard.csv", "adapter": "apple_card"},
    {"file": "inbox/chase_checking.csv", "adapter": "generic_amount",
     "account": "Chase Checking", "institution": "Chase"},
    {"file": "inbox/savings.csv", "adapter": "generic_debit_credit",
     "account": "Ally Savings", "institution": "Ally"}
  ]
}
```

See `assets/sources.example.json`.
