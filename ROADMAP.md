# Roadmap

Where money-map is headed, as a **Now / Next / Later** roadmap. Forward items draw
feature/metric ideas from open-source finance apps, each credited inline:
[Wallos](https://github.com/ellite/Wallos),
[Sure](https://github.com/we-promise/sure) (a Maybe fork),
[Firefly III](https://github.com/firefly-iii/firefly-iii),
[Actual](https://github.com/actualbudget/actual),
[Maybe](https://github.com/maybe-finance/maybe),
[Paisa](https://github.com/ananthakumaran/paisa), and
[Mintable](https://github.com/kevinschaich/mintable).

## Recently shipped

The full pipeline now runs end-to-end in code (`ingest → dedup → enrich → build_dashboard`):

- **`enrich.py`** — category rules (outflow-only), account aliases, recurring/subscription
  detection (cadence, normalized monthly cost, "possibly cancelled"), and net-worth typing
  (cash / investment / credit / loan).
- **`build_dashboard.py`** — a single, self-contained **offline** HTML dashboard (inline
  data + CSS + JS, no network), light/dark, with eight screens.
- **`tests/`** — adapter detection, sign normalization, dedup grouping, enrichment, and a
  full-pipeline build (6 tests, green).

## What's actually in the code today

Being honest about shipped code vs. what the reference docs describe:

| Area | In code (`✅`) | Described in `references/`, not built yet (`📄`) |
|---|---|---|
| Ingestion | ✅ multi-source adapters + auto-detect | — |
| Dedupe | ✅ EXACT/CROSS audit, flag-don't-delete | — |
| Categorize/enrich | ✅ rules, aliases, recurring detection | 📄 subcategory roll-up/filter (column shown, no aggregation) |
| Net worth | ✅ point-in-time (assets − liabilities) | 📄 trend over time (`networth-history.json`) |
| Spending | ✅ by category (bars), merchant, day, income sources | 📄 category treemap, calendar heatmap |
| Recurring | ✅ full (monthly cost, possibly-cancelled) | — |
| Debt & Bills | ✅ balances, "APR not provided" | 📄 utilization, payoff simulator, auto-loan projection |
| Analytics | ✅ averages, top category/merchant, monthly table | 📄 anomalies, YoY, price-creep, cash-flow forecast, safe-to-spend, committed-vs-flexible |
| Ranges | — | 📄 time-range selector (This month / 3M / 12M / All) |

## Now — make the dashboard match its own spec

The highest-priority work is closing the gap between what `references/dashboard.md` promises
and what `build_dashboard.py` currently computes:

1. **Time-range selector** (This month / 3M / 12M / All) with range-aware screens.
2. **Net-worth trend** — accumulate one `networth-history.json` snapshot per build and chart it.
3. **Richer spending views** — category treemap, day-level calendar heatmap, and subcategory
   drill-down/filter (the data already carries `subcategory`).
4. **Debt & Bills** — utilization, a payoff simulator, and auto-loan projection (APR
   user-editable, since sources rarely provide it).
5. **Committed vs flexible** at the transaction level, and **safe-to-spend** on Overview.
6. **Core analytics** — spending anomalies, year-over-year, subscription price-creep, a simple
   cash-flow forecast, and cash runway.
7. **Verification** — a headless render check in `tests/` that loads every screen across each
   range and theme (catches a broken field mapping immediately).

## Next — Tier-1/2 features (from the OSS apps)

1. **Real budgeting**: per-category monthly budgets with rollover/carryover + budget-vs-actual
   trend. (Actual, Firefly, Sure, YNAB.) *Biggest single feature gap.*
2. **Savings-rate metric + trend**: `(income − spend) / income` per month + rolling average. (Paisa/FIRE.)
3. **Bills**: next-expected date, "paid this cycle?" status, and expected-vs-actual amount. (Firefly, Wallos, Paisa.)
4. **Transfers via a `type` field**, not keyword rules — use an explicit internal-transfer type
   (e.g. Copilot's `INTERNAL_TRANSFER`) to clean up every spend metric.
5. **Annualized subscription cost + % of income.** (Wallos.)
6. **Savings goals / piggy banks.** (Firefly, Maybe.)
7. **Tag-based views** — filter and spend-by-tag. (Firefly, Actual.)
8. **Cash-flow statement + money-flow (Sankey)** income → categories. (Firefly, Actual.)
9. **Conditional rules engine** — merchant AND amount/account → category/tag. (Firefly, Actual.)
10. **Recurring income detection** (paycheck cadence) for better projections.

## Later — investments & long horizon (Tier 3/4)

- **Investment holdings analytics**: allocation, cost basis, unrealized gain, dividends —
  needs a holdings feed (Plaid `investments holdings`). (Maybe, Paisa.)
- **Investment return %**: XIRR / time-weighted return. (Paisa.)
- **Net-worth change attribution**: contributions vs. market growth. (Maybe, Paisa.)
- **FIRE / retirement projection** — rough (savings-rate) first, sharper with returns later. (Paisa.)
- **Reconciliation drift check** — flag when a computed running balance diverges from the
  statement balance. (Actual.)
- **Split transactions** — one charge across multiple categories. (Firefly, Actual.)

## Explicitly out of scope

- **Double-entry / ledger rewrite** (Firefly, Paisa) — overkill for a single-user,
  read-only, derived-metrics model.
- **Multi-currency** (Firefly, Wallos, Paisa) — USD-only unless there's demand.
- **Manual transaction entry / write-back** — the pipeline is read-only by design.

## What each app is best at (credit & context)

| App | Core strength (functionality) |
|---|---|
| **Wallos** | Subscription/bill tracker: billing cycle, next-due date, cost normalized to monthly/yearly, reminders. |
| **Sure** (fork of Maybe) | General PFM: net worth, transactions, budgeting, investments, transfers. |
| **Firefly III** | Double-entry PFM: budgets, bills with due-date/paid status, tags, rules engine, piggy banks, rich reports. |
| **Actual** | Envelope / zero-based budgeting: rollover budgets, scheduled txns, rules, reconciliation. |
| **Maybe** | Wealth/net-worth: investment holdings, allocation, return/performance, forecasting. |
| **Paisa** | Ledger-based investing: XIRR/returns, allocation, retirement/FIRE, bill calendar, loan schedules. |
| **Mintable** | ETL: Plaid → Sheets/CSV + categorization. |
