import csv
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)

import adapters
import enrich


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


class AdapterTests(unittest.TestCase):
    def test_detects_builtin_adapters(self):
        self.assertEqual(adapters.detect_adapter(["Transaction Date", "Merchant", "Amount (USD)"]), "apple_card")
        self.assertEqual(adapters.detect_adapter(["Date", "Payee", "Outflow", "Inflow"]), "ynab")
        self.assertEqual(adapters.detect_adapter(["Date", "Description", "Amount", "Transaction Type"]), "mint")

    def test_sign_normalization(self):
        apple = adapters.apply_adapter(
            ["Transaction Date", "Merchant", "Amount (USD)"],
            [{"Transaction Date": "06/01/2026", "Merchant": "Sample Cafe", "Amount (USD)": "12.34"}],
            "apple_card",
        )
        self.assertEqual(apple[0]["amount"], -12.34)

        ynab = adapters.apply_adapter(
            ["Date", "Payee", "Outflow", "Inflow"],
            [{"Date": "2026-06-02", "Payee": "Sample Store", "Outflow": "45.67", "Inflow": ""}],
            "ynab",
        )
        self.assertEqual(ynab[0]["amount"], -45.67)

        mint = adapters.apply_adapter(
            ["Date", "Description", "Amount", "Transaction Type"],
            [
                {"Date": "2026-06-03", "Description": "Sample Store", "Amount": "10.00", "Transaction Type": "debit"},
                {"Date": "2026-06-04", "Description": "Sample Refund", "Amount": "5.00", "Transaction Type": "credit"},
            ],
            "mint",
        )
        self.assertEqual(mint[0]["amount"], -10.0)
        self.assertEqual(mint[1]["amount"], 5.0)


class DedupTests(unittest.TestCase):
    def test_exact_and_cross_are_reported_separately(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "tx.csv")
            report = os.path.join(td, "audit.md")
            fields = ["date", "description", "amount", "account", "institution", "category", "subcategory", "source"]
            write_csv(path, [
                {"date": "2026-06-01", "description": "Sample Market", "amount": "-12.00", "account": "Card A", "institution": "Example", "category": "", "subcategory": "", "source": "one"},
                {"date": "2026-06-01", "description": "Sample Market", "amount": "-12.00", "account": "Card A", "institution": "Example", "category": "", "subcategory": "", "source": "two"},
                {"date": "2026-06-02", "description": "Sample Utility", "amount": "-30.00", "account": "Card A", "institution": "Example", "category": "", "subcategory": "", "source": "one"},
                {"date": "2026-06-02", "description": "Sample Utility", "amount": "-30.00", "account": "Card B", "institution": "Example", "category": "", "subcategory": "", "source": "two"},
            ], fields)
            subprocess.run([sys.executable, os.path.join(SCRIPTS, "dedup.py"), "--in", path,
                            "--audit-only", "--report", report], check=True)
            with open(report, encoding="utf-8") as f:
                text = f.read()
            self.assertIn("EXACT (same date, amount, merchant AND account):** 1 groups", text)
            self.assertIn("CROSS (same date, amount, merchant, DIFFERENT account):** 1 groups", text)


class EnrichTests(unittest.TestCase):
    def test_category_rules_apply_to_outflows_only(self):
        rows = [
            {"date": "2026-06-01", "description": "Sample Coffee", "amount": "-4.50", "account": "", "institution": "", "category": "", "subcategory": "", "source": "test"},
            {"date": "2026-06-02", "description": "Sample Coffee Reimbursement", "amount": "4.50", "account": "", "institution": "", "category": "Income", "subcategory": "", "source": "test"},
        ]
        rules = [{"_match": "sample coffee", "category": "Coffee", "subcategory": "Cafe"}]
        enriched, _recurring = enrich.enrich_rows(rows, category_rules=rules)
        self.assertEqual(enriched[0]["category"], "Coffee")
        self.assertEqual(enriched[0]["subcategory"], "Cafe")
        self.assertEqual(enriched[1]["category"], "Income")

    def test_recurring_detection_thresholds(self):
        rows = []
        for date in ["2026-01-05", "2026-02-05", "2026-03-05", "2026-04-05"]:
            rows.append({"date": date, "description": "Sample Streaming", "amount": "-15.00",
                         "account": "", "institution": "", "category": "Subscriptions",
                         "subcategory": "", "source": "test"})
        enriched, recurring = enrich.enrich_rows(rows, today=enrich.parse_date("2026-04-20"))
        self.assertEqual(len(recurring), 1)
        self.assertEqual(recurring[0]["cadence"], "monthly")
        self.assertEqual(recurring[0]["status"], "active")
        self.assertEqual(enriched[0]["recurring_label"], "Sample Streaming")

    def test_sample_pipeline_builds_dashboard(self):
        with tempfile.TemporaryDirectory() as td:
            canonical = os.path.join(td, "canonical.csv")
            master = os.path.join(td, "master.csv")
            enriched = os.path.join(td, "enriched.csv")
            html = os.path.join(td, "dashboard.html")
            subprocess.run([sys.executable, os.path.join(SCRIPTS, "ingest.py"),
                            "--in", os.path.join(ROOT, "assets", "sample_data"),
                            "--out", canonical], check=True)
            subprocess.run([sys.executable, os.path.join(SCRIPTS, "dedup.py"),
                            "--in", canonical, "--out", master, "--apply",
                            "--report", os.path.join(td, "audit.md")], check=True)
            subprocess.run([sys.executable, os.path.join(SCRIPTS, "enrich.py"),
                            "--in", master, "--out", enriched,
                            "--meta", os.path.join(td, "meta.json")], check=True)
            subprocess.run([sys.executable, os.path.join(SCRIPTS, "build_dashboard.py"),
                            "--in", enriched, "--out", html], check=True)
            with open(html, encoding="utf-8") as f:
                text = f.read()
            self.assertIn("window.FINANCE_DATA", text)
            self.assertIn("Money Map Dashboard", text)
            self.assertNotIn("https://", text)


if __name__ == "__main__":
    unittest.main()
