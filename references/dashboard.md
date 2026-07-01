# Build the dashboard & what each screen shows

The clean `master_transactions.csv` (plus balances/liabilities and the config
CSVs) powers a single **self-contained HTML dashboard**: one file, opens in any
browser, no server and no internet connection required, so the data never leaves
the machine. It supports a light/dark theme and a time-range selector
(This month / 3M / 12M / All) that the period-sensitive screens respect.

This skill focuses on getting trustworthy data *into* the dashboard. The
dashboard itself is a presentation layer you can build from the canonical data
with any chart library; the screens below describe the insights worth providing
and which fields each one needs, so the result is consistent regardless of
implementation.

## Screens and the insight each provides

**Overview** - the at-a-glance answer to "where do I stand?": liquid balance,
net worth, this-period spend and income with change-vs-last-period, a recent
activity feed, and upcoming bills. Lead the headline number with liquid cash, not
net worth, so a large loan balance doesn't make the top figure look alarming.

**Net Worth** - assets minus debt now, plus a trend over time. Accumulate one
snapshot per refresh (a small `networth-history.json`) to draw the trajectory.
Assets and liabilities of every type count here, not just spending accounts:
cash, investments/retirement/crypto (assets) and credit cards, auto loans, and a
mortgage (liabilities) - sourced from Plaid balances/liabilities or
`manual_balances.csv` (see `enrichment.md`).

**Spending** - the deep dive, all range-aware:
- KPI cards (total spent, net saved, top category, subscriptions/month) each with
  a sparkline and an honest **same-period-last-time** delta (comparing a partial
  current month against the same number of days last month keeps it fair);
- a category breakdown sized by share of spend;
- a day-by-day calendar heatmap (brighter = more spent);
- top merchants and income-source composition.

**Recurring / Subscriptions** - everything detected as recurring (see
`enrichment.md`): active subscriptions with estimated monthly cost, recurring
bills, buy-now-pay-later activity, and a "possibly cancelled" list for lapsed
subscriptions. Surfaces forgotten spend.

**Accounts** - balances grouped by institution, with cash vs credit/loan and
recent activity per account; closed/historical accounts kept out of the active
view.

**Debt & Bills** - card balances, utilization, and payoff simulators. Where a
source doesn't provide APR or minimum payment (common for auto loans), show
"not provided" and let the user enter assumptions rather than displaying a
misleading $0.

**Transactions** - the full ledger with filters (month, institution,
account/card, category, subcategory, search). Drilling in from any other screen
should carry the active time period so the numbers reconcile.

**Analytics / Insights** - multi-year views computed from the full history:
spending trend, year-over-year, category movers, spending anomalies (a category
running well above its own typical month), subscription price changes, and a
simple cash-flow forecast - plus auto-generated plain-language insights.

## How the dashboard HTML is built (architecture)

For a user who wants to understand or reproduce the dashboard, the structure is
deliberately simple and inspectable - three plain-text pieces assembled into one
file, no build tools or framework required:

1. **A data file** - a script reads `master_transactions.csv` + balances +
   config CSVs and writes the numbers the UI needs as a single JavaScript object,
   e.g. `window.FINANCE_DATA = { transactions:[...], monthly:{...},
   netWorth:{...}, accounts:[...], recurring:[...], ... }`. This is the "data
   contract": all aggregation happens here, so the UI just renders.
2. **A UI file** - a small component (plain JS + a charting library such as
   Chart.js) that reads `window.FINANCE_DATA` and draws each screen. Categories,
   filters, ranges, and themes are handled here.
3. **A shell** - an HTML template with the fonts, the chart library tag, the CSS
   variables for theming, a root element, and two placeholders.

The "build" simply substitutes the data file and the UI file into the shell's two
placeholders and writes one `Finance Dashboard.html`. Because everything is
inlined, the result opens by double-clicking - offline, no server, nothing
uploaded. To understand any number on screen, a user can open the HTML and read
the `FINANCE_DATA` object, or open the source `master_transactions.csv`.

Keeping data generation (step 1) separate from presentation (step 2) is what
makes it maintainable: fix categorization or dedup in the data step and every
screen updates; restyle a screen without touching the data.

## Build & verify

Assemble the data into the dashboard, then verify before showing the user.
Because the dashboard is one self-contained file, a reliable check is to render
it headlessly (or load every screen in a stub DOM) and confirm each screen
produces output across each time range and theme - this catches a broken field
mapping immediately. Re-run this verification after any change.
