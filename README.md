# money-map

**Turn messy financial exports from every bank and app into one clean, de-duplicated, categorized dataset — and a private local dashboard.**

money-map is an **agent skill** paired with a set of small, dependency-free Python scripts. Point it at a folder of CSV exports (or a live Plaid connection) and it normalizes wildly different formats into one canonical schema, conservatively merges and de-duplicates overlapping sources, categorizes spending with editable rules, detects recurring subscriptions and bills, and builds a self-contained HTML dashboard with spending, net-worth, debt, and trend insights.

It's built on the open [Agent Skills](https://agentskills.io/specification) format, so it isn't tied to any one assistant — it works with any AI coding agent that reads that format (Claude, Codex, Copilot CLI, Gemini CLI, …), or standalone (the ingest + dedup scripts are just Python — see [what's implemented today](#whats-implemented-today)).

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

### What's implemented today

money-map is delivered as **runnable scripts for the data pipeline** plus **reference specs the agent follows** for the enrichment and dashboard stages:

| Stage | Status |
|---|---|
| Normalize (ingest + adapters) | ✅ script — `ingest.py` / `adapters.py` |
| Merge & de-duplicate | ✅ script — `dedup.py` |
| Plaid / Copilot conversion | ✅ scripts — `plaid_to_csv.py`, `copilot_to_csv.py` |
| Categorize & enrich (category rules, recurring detection, account aliases) | 📄 method + editable CSV templates — the agent implements it from [`references/enrichment.md`](references/enrichment.md); no standalone script yet |
| Dashboard | 📄 design contract — built from the canonical data per [`references/dashboard.md`](references/dashboard.md); no standalone builder yet |

So **standalone (no AI), the scripts give you a clean, normalized, de-duplicated dataset.** The categorization/recurring detection and the dashboard are specs for an AI agent (or you) to generate from the reference docs — a `scripts/enrich.py` and `scripts/build_dashboard.py` are the top [roadmap](ROADMAP.md) items.

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

## Using it with an AI agent

money-map is built to be **driven by an AI coding agent** for a non-technical user: you drop exports in a folder and say *"import my transactions"* or *"build me a finance dashboard,"* and the agent runs the pipeline, picks sensible defaults, and asks short plain-language questions only when something needs your judgment. [`SKILL.md`](SKILL.md) is the playbook the agent follows.

Because it uses the open [Agent Skills](https://agentskills.io/specification) format (a `SKILL.md` plus supporting files), you install it by dropping the `money-map/` folder into your agent's skills directory:

| Agent | Where it goes |
|---|---|
| **Claude Code / Claude Desktop** | `~/.claude/skills/money-map/` |
| **OpenAI Codex CLI** | its skills dir, or the cross-runtime `~/.agents/skills/money-map/` |
| **GitHub Copilot CLI** | auto-discovered from installed skills |
| **Gemini CLI** | activates via its skill mechanism |

```bash
# example: Claude Code
git clone https://github.com/djspiceroute/money-map.git ~/.claude/skills/money-map
```

Once installed, the skill activates automatically when you ask about importing transactions, combining statements, tracking net worth, finding subscriptions, or building a budgeting/finance dashboard.

**No skills support?** In a plain chatbot, custom GPT, or project workspace, paste [`SKILL.md`](SKILL.md) in as instructions/context and run the scripts yourself — same playbook. The only hard requirement is that the agent (or you) can **access the filesystem and run Python**; a chat with no code execution can advise on the data but can't run the pipeline.

**No AI at all?** The ingest + dedup scripts are plain stdlib Python — run the [Quickstart](#quickstart-try-it-on-the-bundled-sample-data) to get a clean, de-duplicated dataset. (Enrichment and the dashboard are agent/reference-driven — see [what's implemented today](#whats-implemented-today).)

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
├── SKILL.md                 # the skill the agent follows (start here)
├── ROADMAP.md               # feature ideas + credit to the OSS apps that inspired them
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

## Roadmap

See [ROADMAP.md](ROADMAP.md) for prioritized feature ideas — real budgeting, savings-rate, bill due/paid status, investment analytics, and more — each credited to the open-source app that inspired it.

## Contributing

Adapters for more banks/apps are the most useful contributions — most are a single dict in `scripts/adapters.py` plus a note in `references/source-adapters.md`. Please keep the scripts dependency-free (stdlib only) and never commit real financial data.

## Credits & acknowledgements

money-map stands on other people's work:

**Integrations**
- [**Plaid**](https://plaid.com) and its official [Plaid CLI](https://plaid.com/docs/resources/cli/) — the optional live bank connection (balances, liabilities, transactions), running locally.
- [**copilot-money-cli**](https://github.com/JaviSoto/copilot-money-cli) by [**JaviSoto**](https://github.com/JaviSoto) — the unofficial community CLI used to pull Copilot Money data without a manual export.

**Export formats adapted** — thanks to the apps whose CSV exports the built-in adapters read: Apple Card, [Copilot Money](https://copilot.money), Mint, [Monarch Money](https://www.monarchmoney.com), and [YNAB](https://www.ynab.com).

**Feature & metric inspiration** — the roadmap draws ideas from these excellent open-source finance projects: [Wallos](https://github.com/ellite/Wallos), [Sure](https://github.com/we-promise/sure), [Firefly III](https://github.com/firefly-iii/firefly-iii), [Actual](https://github.com/actualbudget/actual), [Maybe](https://github.com/maybe-finance/maybe), [Paisa](https://github.com/ananthakumaran/paisa), and [Mintable](https://github.com/kevinschaich/mintable).

**Built with** [Claude Code](https://claude.com/claude-code) — the skill, pipeline, and docs were designed and iterated with Claude.

## License

[MIT](LICENSE) — © 2026 djspiceroute.

*Not affiliated with Plaid, Copilot Money, Apple, Mint, Monarch, YNAB, or any project listed above. This is a personal-use tool, not financial advice.*
