"""Tests for Yorkshire Water historical statistics import helpers."""

from __future__ import annotations

from datetime import date
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]


def _load_statistics_import_module():
    """Load statistics_import.py without importing Home Assistant."""
    package = types.ModuleType("custom_components.yorkshire_water")
    package.__path__ = [str(ROOT / "custom_components/yorkshire_water")]
    sys.modules["custom_components.yorkshire_water"] = package

    for name in ("const", "api", "statistics_import"):
        spec = importlib.util.spec_from_file_location(
            f"custom_components.yorkshire_water.{name}",
            ROOT / f"custom_components/yorkshire_water/{name}.py",
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)

    return sys.modules["custom_components.yorkshire_water.statistics_import"]


statistics_import = _load_statistics_import_module()


CSV_SAMPLE = """Time Period:,June 2026
Average daily usage:,148 litres,£0
Date,Litres,£,£ (inc. sewerage)
Total,126,£0.25,£0.57
01 Mon,94,£0.19,£0.43
02 Tue,32,£0.06,£0.14
"""


class YorkshireWaterStatisticsImportTests(unittest.TestCase):
    """Test historical statistics import helpers."""

    def test_parse_yorkshire_water_csv_month_and_daily_rows(self) -> None:
        rows = statistics_import.parse_yorkshire_water_csv(CSV_SAMPLE)

        self.assertEqual([row.day for row in rows], [date(2026, 6, 1), date(2026, 6, 2)])
        self.assertEqual([row.litres for row in rows], [94.0, 32.0])
        self.assertEqual(rows[0].cubic_metres, 0.094)
        self.assertEqual(rows[0].clean_water_cost, 0.19)
        self.assertEqual(rows[0].total_cost, 0.43)

    def test_csv_ignores_total_row_but_validates_total_litres(self) -> None:
        rows = statistics_import.parse_yorkshire_water_csv(CSV_SAMPLE)
        self.assertEqual(sum(row.litres for row in rows), 126.0)

        with self.assertRaisesRegex(
            statistics_import.YorkshireWaterStatisticsImportError,
            "total litres",
        ):
            statistics_import.parse_yorkshire_water_csv(
                CSV_SAMPLE.replace("Total,126", "Total,127")
            )

    def test_build_cumulative_statistics_rows(self) -> None:
        rows = statistics_import.parse_yorkshire_water_csv(CSV_SAMPLE)
        stats = statistics_import.build_cumulative_statistics_rows(
            rows,
            timezone=ZoneInfo("Europe/London"),
        )

        self.assertEqual(len(stats), 3)
        self.assertEqual(stats[0]["start"].date(), date(2026, 6, 1))
        self.assertEqual(stats[0]["state"], 0)
        self.assertEqual(stats[0]["sum"], 0)
        self.assertEqual(stats[1]["start"].date(), date(2026, 6, 2))
        self.assertEqual(stats[1]["state"], 0.094)
        self.assertEqual(stats[1]["sum"], 0.094)
        self.assertEqual(stats[2]["start"].date(), date(2026, 6, 3))
        self.assertEqual(stats[2]["state"], 0.126)
        self.assertEqual(stats[2]["sum"], 0.126)
        self.assertIsNotNone(stats[0]["start"].tzinfo)

    def test_build_import_plan_and_dry_run_report(self) -> None:
        rows = statistics_import.parse_yorkshire_water_csv(CSV_SAMPLE)
        plan = statistics_import.build_import_statistics_plan(
            rows,
            timezone=ZoneInfo("Europe/London"),
            prior_stats=[{"state": 10.0, "sum": 10.0}],
        )
        report = statistics_import.build_dry_run_report(
            source="csv",
            statistic_id="sensor.yorkshire_water_estimated_cumulative_usage",
            plan=plan,
        )

        self.assertEqual(report["daily_rows_parsed"], 2)
        self.assertEqual(report["earliest_date"], "2026-06-01")
        self.assertEqual(report["latest_date"], "2026-06-02")
        self.assertEqual(report["total_litres"], 126.0)
        self.assertEqual(report["total_m3"], 0.126)
        self.assertEqual(report["base_cumulative_m3"], 10.0)
        self.assertEqual(report["final_cumulative_m3"], 10.126)
        self.assertFalse(report["existing_statistics_overlap"])

    def test_rejects_malformed_csv_safely(self) -> None:
        with self.assertRaisesRegex(
            statistics_import.YorkshireWaterStatisticsImportError,
            "Time Period",
        ):
            statistics_import.parse_yorkshire_water_csv("Date,Litres\n01 Mon,94\n")

        secret = "SECRET-SHOULD-NOT-APPEAR"
        with self.assertRaises(statistics_import.YorkshireWaterStatisticsImportError) as err:
            statistics_import.parse_yorkshire_water_csv(
                CSV_SAMPLE.replace("01 Mon,94", f"01 Mon,{secret}")
            )
        self.assertNotIn(secret, str(err.exception))

    def test_rejects_duplicate_dates(self) -> None:
        duplicate = CSV_SAMPLE + "02 Tue,1,£0.01,£0.01\n"
        with self.assertRaisesRegex(
            statistics_import.YorkshireWaterStatisticsImportError,
            "duplicate",
        ):
            statistics_import.parse_yorkshire_water_csv(duplicate)

    def test_rejects_overlapping_import_unless_allowed(self) -> None:
        rows = statistics_import.parse_yorkshire_water_csv(CSV_SAMPLE)
        overlap = [{"state": 1.0, "sum": 1.0}]

        with self.assertRaisesRegex(
            statistics_import.YorkshireWaterStatisticsImportError,
            "overlap",
        ):
            statistics_import.build_import_statistics_plan(
                rows,
                timezone=ZoneInfo("Europe/London"),
                overlapping_stats=overlap,
            )

        plan = statistics_import.build_import_statistics_plan(
            rows,
            timezone=ZoneInfo("Europe/London"),
            overlapping_stats=overlap,
            allow_overwrite=True,
        )
        self.assertTrue(plan.existing_statistics_overlap)
        self.assertEqual(plan.overlap_count, 1)

    def test_api_periods_convert_litres_to_m3(self) -> None:
        rows = statistics_import.daily_rows_from_api_periods(
            [
                {"start": "2026-06-01", "value_litres": 94},
                {"start": "2026-06-02", "value_m3": 0.032},
            ]
        )

        self.assertEqual([row.litres for row in rows], [94.0, 32.0])
        self.assertEqual([row.cubic_metres for row in rows], [0.094, 0.032])


if __name__ == "__main__":
    unittest.main()
