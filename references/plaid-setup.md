# Live bank data via Plaid (optional)

Most users can rely on CSV/app exports alone. A live connection is useful when
someone wants current balances and liabilities (credit-card APR, minimum
payment, due date) on top of transactions. This uses the **official Plaid CLI**,
which runs locally - credentials and data stay on the user's machine. Reference:
https://plaid.com/docs/resources/cli/ . The CLI is officially marked
**experimental**, so verify commands against that page (`plaid --help` shows the
live command tree) - the details below were accurate as of mid-2026.

## Getting started from zero (free, real bank data)

A non-technical user can do this in ~15 minutes, entirely from the terminal. The
official CLI can even create the account and apply for the free Trial plan for
you.

**1. Install the CLI** (macOS, via Homebrew):

```bash
brew install plaid/plaid-cli/plaid
plaid --version            # verify
```

**2. Create an account and log in.** `plaid register` opens the signup page in a
browser; after verifying the account, `plaid login` authenticates and **fetches
the API keys automatically** (no copy-pasting secrets):

```bash
plaid register            # opens dashboard signup (skip if already have an account)
plaid login               # authenticate; stores + refreshes tokens locally
```

**3. Turn on real bank data (Trial plan).** New accounts default to **Sandbox**
(fake data). To connect real banks, apply for the free **Trial plan** and refresh
keys once approved (auto-approved for most personal users):

```bash
plaid trial               # opens the Trial plan application in the browser
plaid keys fetch          # refresh local keys after approval -> Production
```

As of this writing the Trial plan is free, gives **real Production data**, supports
roughly **10 linked banks**, and includes the products this skill uses (Transactions,
Balance, Liabilities, Investments) across most major US/Canada banks (Chase, Bank of
America, Wells Fargo, etc.); Non-US/Canada institutions aren't on Trial. Plaid's plan
names, limits, and pricing change over time — **confirm the current terms in the Plaid
dashboard** rather than relying on these numbers.

**4. Link the user's banks.** `plaid link` opens Plaid Link in the browser; the
user logs into each bank as they normally would - the CLI never sees the bank
password, only a token, which it saves automatically. Request the products you
need and list what's linked:

```bash
plaid link --products transactions,liabilities,investments
plaid item list           # confirm linked banks
```

**Dry run with fake data first (optional).** To try the mechanics before
connecting real accounts, use Sandbox:

```bash
plaid config set --env sandbox
plaid sandbox link --products transactions,liabilities
```

Then continue with **Pulling data** below.

## Pulling data

Every command supports `--json` (primary result on stdout, diagnostics on
stderr) - ideal for feeding this pipeline. Use `--all` for every linked bank or
`--item <alias>` for one. Run `plaid <command> --help` for current flags.

```bash
# Transactions as JSON (then convert with plaid_to_csv.py)
plaid transactions list --all --count 500 --json > plaid_dump.json
python scripts/plaid_to_csv.py plaid_dump.json --out plaid_canonical.csv

# Current balances and liabilities (for net worth / debt screens)
plaid balance --all --json
plaid liabilities --all --json
```

For ongoing automation, `plaid transactions sync` is cursor-based and only
returns what changed since last time - ideal for a monthly refresh.

### Investments, retirement & mortgage (balance level)

`plaid balance` returns current **investment** account values (brokerage,
IRA/401k) alongside cash, and `plaid liabilities` returns **mortgage** and
student-loan details (balance, rate, term, due date). Feed these into net worth
the same way as everything else (see the `manual_balances.csv` type taxonomy in
`enrichment.md`: cash / investment / credit / loan). This gives a complete net
worth - assets minus liabilities - without modeling individual positions.

The CLI can also return **per-holding** detail via `plaid investments holdings`
(security, ticker, quantity, price, value) and `plaid investments transactions`
(buys/sells/dividends). Showing those as an allocation/positions view is a
separate feature beyond the balance-level net-worth scope here, but the data is
one command away if you extend the skill later.

## Important gotchas

- **Sign:** Plaid uses positive = money out, the opposite of our convention.
  `plaid_to_csv.py` inverts it automatically. If you ever parse Plaid yourself,
  remember to flip the sign.
- **History depth varies:** how far back the first transactions pull goes depends
  on the bank and plan (often up to ~24 months, sometimes less). For years of
  history, pair Plaid (recent top-up) with a finance-app export (the long
  backbone) and let `dedup.py` reconcile the overlap.
- **10-bank cap on Trial:** the free Trial plan allows up to 10 linked
  institutions; that's plenty for most people but worth knowing before linking.
- **Auto loans:** liabilities returns APR / minimum payment / due date for credit
  cards (and student/mortgage), but auto loans usually return **balance only**.
  Surface APR/term as user-editable when building the debt screen.
- **Generic account names:** Plaid sometimes returns names like "CREDIT CARD".
  Rename them via `account_aliases.csv` (see `enrichment.md`).
- **Login cadence:** sessions expire periodically, so a fully unattended refresh
  is unreliable - treat the refresh as assisted (the user runs it, you help).

## Accounts that can't connect

Some issuers don't expose data to Plaid (Apple Card is the common example).
Handle these with manual CSV exports (the `apple_card` adapter) and, for
balances those exports omit, a `manual_balances.csv` (account, balance, type)
that the build step adds into net worth.
