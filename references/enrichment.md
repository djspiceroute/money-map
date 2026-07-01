# Categorize & enrich

The goal of this stage is a dataset that is meaningful and that the user can
correct without touching code. Everything is driven by small editable CSVs, so a
mistake is a one-line fix plus a rebuild - never a code change. Keep all of these
in a `config/` folder next to the data.

## 1. Category rules - `merchant_categories.csv`

Columns: `match,category` (an optional third `note` column is ignored by code).
A case-insensitive **substring** of the description maps to a category.

```
match,category
starbucks,Coffee
whole foods,Groceries
shell,Gas
netflix,Subscriptions
```

Two rules that prevent the most common mistakes:

- **Apply to outflows only.** Never let a merchant rule recategorize income or
  reimbursements (e.g. a payroll deposit that happens to contain a vendor name).
- **Order matters - specific before general.** Put `costco gas,Gas` before
  `costco,Warehouse`, and a `... fee,Fees` rule before a broader brand rule.

Goal to aim for: shrink the residual "Other"/uncategorized bucket. Anything large
and uncategorized is the highest-value thing to add a rule for.

### Subcategories

The canonical schema carries a `subcategory` alongside `category` (e.g.
Restaurants / Coffee / Fast Food under a Food & Dining category). It's populated
three ways, in order: a source's own subcategory/"detailed category" column; the
tail of a hierarchical category like `Food and Drink > Restaurants` (split
automatically); or, for spend that a rule sets a category on but leaves no finer
detail, a `Needs Review` placeholder so you can see what still needs a rule.

To assign subcategories yourself, add a `subcategory` column to
`merchant_categories.csv` rows (`match,category,subcategory`) - the same
outflow-only, specific-before-general rules apply. The dashboard's Transactions
screen exposes a subcategory filter and column so these drive real drilldowns.

## 2. Account aliases - `account_aliases.csv`

Columns: `match,account,institution`. Collapse generic or duplicated labels into
one real account and group it under an institution.

```
match,account,institution
CREDIT CARD,Everyday Card,Example Bank
Unlimited Cash Rewards,Cash Rewards Card,Example Bank
```

Also use this to mark closed/historical accounts so they don't clutter the active
Accounts screen (e.g. an `aliases` note or a separate `closed_accounts.csv`
listing account names to treat as closed).

## 3. Recurring detection (subscriptions & bills)

Recurring charges are detected from the data itself by **amount-repetition over
time**, so it works even for merchants no rule knows about. A merchant is treated
as recurring when, over roughly the last 12-18 months, it has:

- at least 3 charges, in at least 3 separate months, and
- those charges cluster around a **stable amount** - within ~15% of the median,
  with a majority of charges near the median - and
- a regular cadence - the **median gap** between charges is at least ~11 days.

Cadence is inferred from the median gap: ~monthly (24-38 days), ~quarterly
(80-100), ~annual (330-400); anything else is "irregular". Monthly cost is
normalized as `amount * 30.44 / median_gap` so quarterly/annual bills compare
fairly against monthly ones.

Deliberately excluded so the list stays meaningful:
- everyday spend categories (Groceries, Restaurants, Coffee, Gas, Fast Food) -
  frequent same-price coffee is a habit, not a bill;
- card payments, transfers, and buy-now-pay-later installments (Affirm, Klarna,
  Pay-in-4) - they aren't subscriptions and distort the totals;
- dust below ~$2/month.

A recurring merchant whose charges **stop for longer than its expected cadence**
(e.g. a monthly sub unseen for 60+ days) is flagged **"possibly cancelled"** -
useful for catching forgotten or lapsed subscriptions.

## 4. Friendly names - `recurring_labels.csv`

Columns: `match,label,category`. Rename cryptic bank descriptors to human names
for the recurring/bills screens.

```
match,label,category
autodraft,Auto Loan,Debt
monthly maintenance,Bank Fee,Fees
```

## 5. Manual balances & all asset types - `manual_balances.csv`

Columns: `account,balance,type`. This is how **any** account becomes part of net
worth, not just spending accounts. It covers two cases: accounts whose exports
omit a current balance (e.g. Apple Card), and whole asset/liability classes that
have no transaction feed at all (investments, property, a mortgage).

`type` taxonomy and how each is treated in net worth:

| type | examples | net worth |
|---|---|---|
| `cash` | checking, savings, money market | asset (+) |
| `investment` | brokerage, IRA/401k, crypto wallet, commodities, bonds | asset (+) |
| `credit` | credit cards | liability (-) |
| `loan` | mortgage, auto loan, student loan | liability (-) |

Enter liability balances as **negative** numbers. Anything you can name and put a
current value on - a Fidelity brokerage, a Vanguard IRA, a Coinbase balance, a
home's estimated value, a mortgage payoff - rolls straight into Net Worth and
appears on the Accounts screen. Nothing breaks if you have none of these; they
simply don't appear.

For accounts that **do** have a live feed, prefer pulling the balance
automatically instead of hand-entering it: Plaid `balance` returns investment and
cash account values, and Plaid `liabilities` returns mortgage/student-loan
balances (see `plaid-setup.md`). Use `manual_balances.csv` for everything Plaid
can't reach (Apple Card, property estimates, an exchange Plaid doesn't support).

This skill tracks these at the **balance / net-worth level**. Position-level
investment detail (individual tickers, cost basis, allocation, dividends) is a
separate, larger feature - Plaid exposes it via `investments holdings` /
`investments transactions` - and would need its own holdings schema and screen.

## Committed vs flexible (optional)

For a "how much of my spend is non-negotiable" view, classify spend at the
transaction level rather than by whole category: treat rent/housing bills,
utilities, loan and card payments, insurance, subscriptions, and detected
recurring obligations as **committed**; leave one-off fuel, rideshare, dining,
shopping, and travel as **flexible**. Doing it per-transaction avoids the trap of
calling an entire category committed when it mixes bills and discretionary spend.
