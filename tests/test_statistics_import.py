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


class YorkshireWaterServiceRegistrationTests(unittest.TestCase):
    """Test Home Assistant service registration smoke behavior."""

    def setUp(self) -> None:
        _install_homeassistant_service_stubs()

    def test_service_schema_accepts_csv_dry_run_payload(self) -> None:
        schema = statistics_import.build_import_statistics_service_schema()

        validated = schema(
            {
                "source": "csv",
                "file_path": "/config/yorkshire_water/June 2026.csv",
                "dry_run": True,
                "allow_overwrite": False,
            }
        )

        self.assertEqual(validated["source"], "csv")
        self.assertEqual(
            validated["entity_id"],
            "sensor.yorkshire_water_estimated_cumulative_usage",
        )
        self.assertEqual(
            validated["file_path"],
            "/config/yorkshire_water/June 2026.csv",
        )
        self.assertIs(validated["dry_run"], True)
        self.assertIs(validated["allow_overwrite"], False)

    def test_service_schema_rejects_invalid_source(self) -> None:
        schema = statistics_import.build_import_statistics_service_schema()

        with self.assertRaises(ValueError):
            schema({"source": "spreadsheet", "file_path": "/config/example.csv"})

    def test_registers_and_unregisters_import_statistics_service(self) -> None:
        integration = _load_integration_module()
        hass = _FakeHass()

        integration.async_register_import_statistics_service(hass)
        integration.async_register_import_statistics_service(hass)

        self.assertEqual(len(hass.services.registered), 1)
        registration = hass.services.registered[0]
        self.assertEqual(registration["domain"], "yorkshire_water")
        self.assertEqual(registration["service"], "import_statistics")
        self.assertEqual(registration["supports_response"], "only")
        self.assertTrue(callable(registration["handler"]))

        integration.async_unregister_import_statistics_service(hass)

        self.assertEqual(
            hass.services.removed,
            [("yorkshire_water", "import_statistics")],
        )


class _Marker:
    def __init__(self, key: str, *, required: bool, default=...):
        self.key = key
        self.required = required
        self.default = default

    def __hash__(self) -> int:
        return hash((self.key, self.required, self.default))

    def __eq__(self, other) -> bool:
        if isinstance(other, _Marker):
            return (
                self.key,
                self.required,
                self.default,
            ) == (other.key, other.required, other.default)
        return self.key == other


class _Schema:
    def __init__(self, schema: dict) -> None:
        self.schema = schema

    def __call__(self, data: dict) -> dict:
        validated = dict(data)
        for marker, validator in self.schema.items():
            key = marker.key if isinstance(marker, _Marker) else marker
            required = isinstance(marker, _Marker) and marker.required
            default = marker.default if isinstance(marker, _Marker) else ...
            if key not in validated:
                if default is not ...:
                    validated[key] = default
                elif required:
                    raise ValueError(f"missing required key: {key}")
                else:
                    continue
            validated[key] = validator(validated[key])
        return validated

    def __contains__(self, key: object) -> bool:
        return any(
            (marker.key if isinstance(marker, _Marker) else marker) == key
            for marker in self.schema
        )


class _VoluptuousModule(types.ModuleType):
    def __init__(self) -> None:
        super().__init__("voluptuous")

    def Schema(self, schema: dict) -> _Schema:
        return _Schema(schema)

    def Required(self, key: str):
        return _Marker(key, required=True)

    def Optional(self, key: str, *, default=...):
        return _Marker(key, required=False, default=default)

    def In(self, values):
        def _validate(value):
            if value not in values:
                raise ValueError(f"value must be one of {values}")
            return value

        return _validate


class _FakeServices:
    def __init__(self) -> None:
        self.registered: list[dict] = []
        self.removed: list[tuple[str, str]] = []

    def async_register(self, domain, service, handler, *, schema=None, supports_response=None):
        self.registered.append(
            {
                "domain": domain,
                "service": service,
                "handler": handler,
                "schema": schema,
                "supports_response": supports_response,
            }
        )

    def async_remove(self, domain, service):
        self.removed.append((domain, service))


class _FakeHass:
    def __init__(self) -> None:
        self.data = {}
        self.services = _FakeServices()


def _install_homeassistant_service_stubs() -> None:
    """Install minimal Home Assistant stubs for service schema tests."""
    homeassistant = sys.modules.setdefault("homeassistant", types.ModuleType("homeassistant"))
    const = types.ModuleType("homeassistant.const")
    core = types.ModuleType("homeassistant.core")
    exceptions = types.ModuleType("homeassistant.exceptions")
    helpers = types.ModuleType("homeassistant.helpers")
    cv = types.ModuleType("homeassistant.helpers.config_validation")

    const.CONF_ENTITY_ID = "entity_id"
    const.Platform = types.SimpleNamespace(SENSOR="sensor")
    core.HomeAssistant = type("HomeAssistant", (), {})
    core.SupportsResponse = types.SimpleNamespace(ONLY="only")
    exceptions.ConfigEntryAuthFailed = type("ConfigEntryAuthFailed", (Exception,), {})
    exceptions.HomeAssistantError = type("HomeAssistantError", (Exception,), {})
    exceptions.ServiceValidationError = type("ServiceValidationError", (Exception,), {})
    cv.entity_id = _validate_entity_id
    cv.string = _validate_string
    cv.boolean = _validate_boolean
    cv.date = _validate_date

    homeassistant.const = const
    homeassistant.core = core
    sys.modules["homeassistant.const"] = const
    sys.modules["homeassistant.core"] = core
    sys.modules["homeassistant.exceptions"] = exceptions
    sys.modules["homeassistant.helpers"] = helpers
    sys.modules["homeassistant.helpers.config_validation"] = cv
    sys.modules["voluptuous"] = _VoluptuousModule()


def _load_integration_module():
    """Load __init__.py with enough Home Assistant stubs for service tests."""
    _install_homeassistant_service_stubs()
    config_entries = types.ModuleType("homeassistant.config_entries")
    aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")
    update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")

    config_entries.ConfigEntry = type("ConfigEntry", (), {})
    aiohttp_client.async_get_clientsession = lambda hass: None
    update_coordinator.DataUpdateCoordinator = type("DataUpdateCoordinator", (), {})
    update_coordinator.UpdateFailed = type("UpdateFailed", (Exception,), {})

    sys.modules["homeassistant.config_entries"] = config_entries
    sys.modules["homeassistant.helpers.aiohttp_client"] = aiohttp_client
    sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator

    spec = importlib.util.spec_from_file_location(
        "custom_components.yorkshire_water.__init__",
        ROOT / "custom_components/yorkshire_water/__init__.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _validate_entity_id(value: str) -> str:
    if not isinstance(value, str) or "." not in value:
        raise ValueError("invalid entity_id")
    return value


def _validate_string(value) -> str:
    if not isinstance(value, str):
        raise ValueError("invalid string")
    return value


def _validate_boolean(value) -> bool:
    if not isinstance(value, bool):
        raise ValueError("invalid boolean")
    return value


def _validate_date(value):
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError("invalid date")


if __name__ == "__main__":
    unittest.main()
