# Refreshing the data

Personal finance data is never "done" - new transactions arrive constantly. Keep
the dataset current with a simple recurring routine. Monthly is plenty for most
people; weekly if they want a tighter pulse.

## The refresh loop

1. **Re-export / re-pull** only what changed:
   - app/bank CSVs: export a fresh file (or just the new date range);
   - Plaid: `plaid transactions sync` (cursor-based, returns only new activity)
     plus `plaid balance --all` / `plaid liabilities --all` for current numbers.
2. **Normalize** the new files: `python ingest.py --in <folder> --out canonical_transactions.csv`.
3. **Merge & audit**: `python dedup.py --in canonical_transactions.csv [others] --audit-only`,
   review, then produce the master with `--apply` once happy.
4. **Rebuild** the dashboard from the master + config CSVs.
5. The build appends one net-worth snapshot so the trend chart grows over time.

## Make it effortless for the user

- Keep a single `inbox/` folder; the user just drops new exports there and says
  "refresh". Auto-detection handles the formats.
- **Optional - schedule it.** If the agent supports scheduled/recurring tasks
  (e.g. Claude Cowork, or any cron-style runner), offer to set up a **scheduled
  task** (e.g. "on the 1st of each
  month") that reminds them to refresh and kicks off the pipeline. Phrase the
  scheduled prompt as a reminder-plus-run, e.g. *"Remind me to refresh my finance
  dashboard: pull the latest Plaid data and re-run ingest -> dedup -> build."*
  Because a live Plaid pull needs the machine awake and an occasional re-login,
  treat the scheduled run as **assisted**: it prompts the user and you walk the
  steps, rather than running fully unattended. (CSV-only refreshes, where the user
  has already dropped exports in `inbox/`, can be closer to hands-off.)
- Treat a live (Plaid) refresh as **assisted**, not unattended: logins expire and
  the machine must be awake, so the user kicks it off and you run the steps.
- Never overwrite the previous master in place without keeping a copy - a bad
  export shouldn't be able to destroy good history.

## Health checks worth running each refresh

- Spend signs still correct (purchases negative)?
- Did the duplicate audit surface anything new (especially in the overlap between
  a fresh Plaid pull and the app backbone)?
- Is the "Other"/uncategorized bucket creeping up? If so, add a couple of
  `merchant_categories.csv` rules for the biggest offenders.
