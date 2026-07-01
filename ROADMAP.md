# Roadmap & feature ideas

Ideas for extending money-map, with credit to the open-source finance apps that
inspired them. The focus here is **functionality and metrics** we can adapt to
the existing pipeline/dashboard — not UI. Apps reviewed for inspiration:
[Wallos](https://github.com/ellite/Wallos),
[Sure](https://github.com/we-promise/sure) (a Maybe fork),
[Firefly III](https://github.com/firefly-iii/firefly-iii),
[Actual](https://github.com/actualbudget/actual),
[Maybe](https://github.com/maybe-finance/maybe),
[Paisa](https://github.com/ananthakumaran/paisa), and
[Mintable](https://github.com/kevinschaich/mintable).

## What each app is best at (one line)

| App | Core strength (functionality) |
|---|---|
| **Wallos** | Subscription/bill tracker: billing cycle, next-due date, cost normalized to monthly/yearly, per-category & per-payer totals, reminders. |
| **Sure** (fork of Maybe) | General PFM: net worth across accounts, transactions, budgeting (trends, overages), investments, transfers. |
| **Firefly III** | Double-entry PFM: budgets, bills with expected due-date + paid/unpaid status, categories, tags, rules engine, piggy banks (savings goals), recurring txns, rich reports. |
| **Actual** | Envelope / zero-based budgeting (YNAB-style): rollover budgets, "to budget" balance, scheduled txns, rules, reconciliation, cash-flow & net-worth reports. |
| **Maybe** | Wealth/net-worth: accounts + investment holdings, allocation, return/performance, forecasting. |
| **Paisa** | Ledger-based investing: XIRR/returns, asset allocation, retirement/FIRE planning, capital gains, credit-card bill calendar, loan/interest schedules, live prices. |
| **Mintable** | ETL only: Plaid → Sheets/CSV + categorization. |

## What money-map already covers (parity or better)

- Net worth + trend over time (Maybe/Sure/Firefly).
- Spending by category / subcategory / merchant / time, calendar heatmap, income sources.
- Recurring & subscription detection, possibly-cancelled, BNPL, monthly cost — most apps make you enter subscriptions by hand; money-map detects them.
- Debt: balances, utilization, payoff simulator + auto-loan projection.
- Analytics many don't have: spending anomalies, subscription price-creep, YoY, cash-flow forecast, cash runway, safe-to-spend, committed-vs-flexible.
- Multi-source ingestion + a conservative dedup audit (Mintable-like, but richer).

## Gaps / high-value additions (prioritized by value ÷ effort)

### Tier 1 — high value, mostly from data we already have

1. **Real budgeting: per-category monthly budgets with rollover/carryover + budget-vs-actual trend.** (Actual, Firefly, Sure, YNAB.) Today there's only a light "budget pressure." Add editable budgets, "left to budget," and a budget-vs-actual line over months. *Biggest single gap.*
2. **Savings-rate metric + trend.** (Paisa/FIRE tools.) `(income − spend) / income` per month, plus a rolling average.
3. **Bills: due-date + "paid this cycle?" status + expected vs actual amount.** (Firefly bills, Paisa calendar, Wallos.) Add per-bill next expected date, whether it's already hit this cycle, and flag when the charged amount deviates from the norm.
4. **Transfers via a `type` field, not category strings.** Where a source provides an explicit internal-transfer type (e.g. Copilot's `INTERNAL_TRANSFER`), use it to exclude transfers cleanly — more reliable than keyword rules, and it improves every spend metric.
5. **Annualized subscription cost + % of income.** (Wallos.) Add total annual subscription spend and subscriptions as a % of income.

### Tier 2 — high value, modest effort

6. **Savings goals / piggy banks.** (Firefly, Maybe.) Where a source exposes a goal link, surface goal contributions and progress.
7. **Tag-based views.** (Firefly, Actual.) Flow source tags through and add a tag filter + spend-by-tag.
8. **Cash-flow statement + money-flow (Sankey) income → categories.** (Firefly, Actual.)
9. **Rules engine beyond substring.** (Firefly, Actual.) Extend `merchant_categories.csv` to conditional rules (merchant AND amount/account → category/tag).
10. **Recurring *income* detection** (paycheck cadence), feeding better projections and a "next paycheck" on Overview.

### Tier 3 — high value but needs new data (investments)

11. **Investment holdings analytics: allocation, cost basis, unrealized gain, dividends.** (Maybe, Paisa.) Needs a holdings feed (Plaid `investments holdings`).
12. **Investment return %: XIRR / time-weighted return.** (Paisa.) Needs holdings + cash-flow dates.
13. **Net-worth change attribution: contributions vs market growth.** (Maybe, Paisa.)
14. **FIRE / retirement projection.** (Paisa.) Rough (savings-rate based) now, sharper with investment returns later.

### Tier 4 — nice-to-have

15. **Reconciliation drift check.** (Actual.) Flag when a computed running balance diverges from the statement balance.
16. **Split transactions** (one charge across multiple categories). (Firefly, Actual.)

## Explicitly out of scope

- **Double-entry / ledger rewrite** (Firefly, Paisa) — overkill for a single-user, read-only, derived-metrics model.
- **Multi-currency** (Firefly, Wallos, Paisa) — USD-only unless there's demand.
- **Manual transaction entry / write-back** — the pipeline is read-only by design.

## Suggested next steps

Quickest wins that materially improve the dashboard: **(4) transfer-via-type**,
**(2) savings-rate**, **(5) annualized subs**, then **(1) real budgeting** and
**(3) bill due/paid status** as the flagship features. Investments (Tier 3) is
the largest untapped area but gated on a holdings data source.
