"""Runnable checks for the Ain Token BI project.

    python test_bi.py        (or: python -m unittest test_bi -v)

Verifies the database against the numbers in the specification and checks that
the dashboard's own data layer + KPI logic reproduce them.
"""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

import create_db
from app import compute_kpis, read_sales
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).parent / "app.py")

# Values from the specification (10-row dataset).
EXPECTED_REGION = {"Constantine": 348_000, "Batna": 228_000, "Oran": 195_000,
                   "Béjaïa": 152_000, "Alger": 93_000}
EXPECTED_MODEL = {"Qwen3 30B-A3B": 336_000, "Qwen3 32B": 266_000, "Qwen2.5-Coder 32B": 195_000,
                  "gpt-oss-20b": 165_000, "Llama 3.1 8B": 54_000}
EXPECTED_MONTH = {"2026-01": 113_000, "2026-02": 222_000, "2026-03": 153_000,
                  "2026-04": 310_000, "2026-05": 98_000, "2026-06": 120_000}


class TestSpecDataset(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = Path(tempfile.mkdtemp()) / "ventes.db"
        create_db.build(cls.db)
        cls.df = read_sales(cls.db)

    def test_row_counts(self):
        with sqlite3.connect(self.db) as con:
            counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                      for t in ("customers", "products", "sales")}
        self.assertEqual(counts, {"customers": 5, "products": 5, "sales": 10})

    def test_total_revenue_and_tokens(self):
        self.assertEqual(self.df["revenue"].sum(), 1_016_000)
        self.assertEqual(self.df["quantity"].sum(), 6_800)

    def test_revenue_by_region(self):
        got = self.df.groupby("region")["revenue"].sum().to_dict()
        self.assertEqual(got, EXPECTED_REGION)

    def test_revenue_by_model(self):
        got = self.df.groupby("model")["revenue"].sum().to_dict()
        self.assertEqual(got, EXPECTED_MODEL)

    def test_revenue_by_month(self):
        got = self.df.groupby("month")["revenue"].sum().to_dict()
        self.assertEqual(got, EXPECTED_MONTH)
        self.assertEqual(sorted(got), sorted(EXPECTED_MONTH))   # all 6 months present

    def test_compute_kpis(self):
        k = compute_kpis(self.df)
        self.assertEqual(k["total_revenue"], 1_016_000)
        self.assertEqual(k["total_tokens"], 6_800)
        self.assertEqual(k["avg_invoice"], 101_600)
        self.assertAlmostEqual(k["mom"], 22.448979, places=5)     # June 120,000 vs May 98,000

    def test_kpis_without_previous_month(self):
        self.assertIsNone(compute_kpis(self.df[self.df["month"] == "2026-01"])["mom"])


class TestRichDataset(unittest.TestCase):
    def test_generated_dataset_is_consistent(self):
        db = Path(tempfile.mkdtemp()) / "ventes.db"
        create_db.build(db, rich=True)
        df = read_sales(db)

        self.assertGreater(len(df), 10)
        self.assertEqual(sorted(df["month"].unique()),
                         [f"2026-{m:02d}" for m in range(1, 13)])   # every month present
        self.assertEqual(df["revenue"].sum(), (df["quantity"] * df["unit_price"]).sum())
        self.assertTrue((df["revenue"] > 0).all())
        self.assertIsNotNone(compute_kpis(df)["mom"])


class TestDashboard(unittest.TestCase):
    """Runs app.py end to end through Streamlit's test harness."""

    def test_dashboard_renders(self):
        at = AppTest.from_file(APP, default_timeout=60).run()

        self.assertEqual([e.value for e in at.exception], [])   # no traceback
        self.assertEqual(at.title[0].value, "Ain Token: Sales Dashboard")
        self.assertEqual(
            [(m.label, m.value) for m in at.metric],
            [("Total revenue", "1,016,000 DA"),
             ("Tokens sold", "6,800 M tokens"),
             ("Average invoice value", "101,600 DA"),
             ("MoM revenue growth", "+22.4%")],
        )
        self.assertEqual(len(at.expander), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
