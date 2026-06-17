"""Sensor platform for the Yorkshire Water integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DEFAULT_NAME, DOMAIN


@dataclass(frozen=True, kw_only=True)
class YorkshireWaterSensorEntityDescription(SensorEntityDescription):
    """Description for Yorkshire Water sensors."""

    value_fn: Callable[[dict[str, Any]], Any] = lambda data: None
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] = lambda data: {}


def _period_attrs(
    data: dict[str, Any],
    start_key: str,
    end_key: str,
    prefix: str,
) -> dict[str, Any]:
    """Build common source period attributes."""
    attrs: dict[str, Any] = {
        "source_period_start": data.get(start_key),
        "source_period_end": data.get(end_key),
        "unit": UnitOfVolume.LITERS,
        "last_successful_update": data.get("last_successful_update"),
        "latest_data_date": data.get("latest_data_date"),
        "latest_update_date": data.get("latest_update_date"),
        "included_day_count": data.get(f"{prefix}_included_day_count"),
        "estimated_day_count": data.get(f"{prefix}_estimated_day_count"),
        "missing_day_count": data.get(f"{prefix}_missing_day_count"),
        "total_cost": data.get(f"{prefix}_total_cost"),
        "clean_water_cost": data.get(f"{prefix}_clean_water_cost"),
        "sewerage_cost": data.get(f"{prefix}_sewerage_cost"),
    }
    attrs["source_periods"] = data.get(f"{prefix}_periods") or []
    return attrs


def _cost_attrs(
    data: dict[str, Any],
    start_key: str,
    end_key: str,
    prefix: str,
) -> dict[str, Any]:
    """Build common cost attributes."""
    return {
        "source_period_start": data.get(start_key),
        "source_period_end": data.get(end_key),
        "included_day_count": data.get(f"{prefix}_included_day_count"),
        "estimated_day_count": data.get(f"{prefix}_estimated_day_count"),
        "missing_day_count": data.get(f"{prefix}_missing_day_count"),
        "clean_water_cost": data.get(f"{prefix}_clean_water_cost"),
        "sewerage_cost": data.get(f"{prefix}_sewerage_cost"),
        "total_cost": data.get(f"{prefix}_total_cost"),
        "raw_unit": "GBP",
        "latest_data_date": data.get("latest_data_date"),
        "latest_update_date": data.get("latest_update_date"),
        "last_successful_update": data.get("last_successful_update"),
    }


SENSORS: tuple[YorkshireWaterSensorEntityDescription, ...] = (
    YorkshireWaterSensorEntityDescription(
        key="yesterday_usage",
        translation_key="yesterday_usage",
        name="Yesterday Usage",
        icon="mdi:water",
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        value_fn=lambda data: data.get("yesterday_usage_litres"),
        attrs_fn=lambda data: _period_attrs(
            data,
            "yesterday_start",
            "yesterday_end",
            "yesterday",
        ),
    ),
    YorkshireWaterSensorEntityDescription(
        key="today_usage",
        translation_key="today_usage",
        name="Today Usage",
        icon="mdi:water-outline",
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        value_fn=lambda data: data.get("today_usage_litres"),
        attrs_fn=lambda data: {
            **_period_attrs(data, "today_start", "today_end", "today"),
            "status_detail": data.get("today_status_detail"),
        },
    ),
    YorkshireWaterSensorEntityDescription(
        key="daily_average",
        translation_key="daily_average",
        name="7-Day Average",
        icon="mdi:water-percent",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        value_fn=lambda data: data.get("daily_average_litres"),
        attrs_fn=lambda data: _period_attrs(
            data,
            "daily_average_period_start",
            "daily_average_period_end",
            "daily_average",
        ),
    ),
    YorkshireWaterSensorEntityDescription(
        key="week_to_date",
        translation_key="week_to_date",
        name="Week to Date",
        icon="mdi:water-sync",
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        value_fn=lambda data: data.get("week_to_date_litres"),
        attrs_fn=lambda data: {
            "source_period_start": data.get("week_start"),
            "source_period_end": data.get("week_end") or datetime.now().date().isoformat(),
            "unit": UnitOfVolume.LITERS,
            "last_successful_update": data.get("last_successful_update"),
            "latest_data_date": data.get("latest_data_date"),
            "latest_update_date": data.get("latest_update_date"),
            "included_day_count": data.get("week_to_date_included_day_count"),
            "estimated_day_count": data.get("week_to_date_estimated_day_count"),
            "missing_day_count": data.get("week_to_date_missing_day_count"),
            "total_cost": data.get("week_to_date_total_cost"),
            "clean_water_cost": data.get("week_to_date_clean_water_cost"),
            "sewerage_cost": data.get("week_to_date_sewerage_cost"),
            "source_periods": data.get("week_to_date_periods") or [],
        },
    ),
    YorkshireWaterSensorEntityDescription(
        key="previous_week",
        translation_key="previous_week",
        name="Previous Week",
        icon="mdi:water-check",
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        value_fn=lambda data: data.get("previous_week_litres"),
        attrs_fn=lambda data: _period_attrs(
            data,
            "previous_week_start",
            "previous_week_end",
            "previous_week",
        ),
    ),
    YorkshireWaterSensorEntityDescription(
        key="month_to_date",
        translation_key="month_to_date",
        name="Month to Date",
        icon="mdi:water-plus",
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        value_fn=lambda data: data.get("month_to_date_litres"),
        attrs_fn=lambda data: _period_attrs(
            data,
            "month_start",
            "latest_data_date",
            "month_to_date",
        ),
    ),
    YorkshireWaterSensorEntityDescription(
        key="year_to_date",
        translation_key="year_to_date",
        name="Year to Date",
        icon="mdi:water-plus-outline",
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        value_fn=lambda data: data.get("year_to_date_litres"),
        attrs_fn=lambda data: _period_attrs(
            data,
            "year_start",
            "latest_data_date",
            "year_to_date",
        ),
    ),
    YorkshireWaterSensorEntityDescription(
        key="meter_reading",
        translation_key="meter_reading",
        name="Meter Reading",
        icon="mdi:counter",
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        value_fn=lambda data: data.get("meter_reading_m3"),
        attrs_fn=lambda data: {
            "reading_date": data.get("meter_reading_date"),
            "estimated": data.get("meter_reading_estimated"),
            "status_detail": data.get("meter_reading_status"),
            "raw_unit": UnitOfVolume.CUBIC_METERS,
            "last_successful_update": data.get("last_successful_update"),
        },
    ),
    YorkshireWaterSensorEntityDescription(
        key="estimated_cumulative_usage",
        translation_key="estimated_cumulative_usage",
        name="Estimated Cumulative Usage",
        icon="mdi:water-pump",
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        value_fn=lambda data: data.get("estimated_cumulative_usage_m3"),
        attrs_fn=lambda data: {
            "source": data.get("estimated_cumulative_source"),
            "raw_unit": data.get("estimated_cumulative_raw_unit"),
            "unit": data.get("estimated_cumulative_unit"),
            "total_litres": data.get("estimated_cumulative_total_litres"),
            "source_total_litres": data.get("estimated_cumulative_source_total_litres"),
            "earliest_source_date": data.get(
                "estimated_cumulative_earliest_source_date"
            ),
            "latest_source_date": data.get("estimated_cumulative_latest_source_date"),
            "included_day_count": data.get("estimated_cumulative_included_day_count"),
            "estimated": data.get("estimated_cumulative_estimated"),
            "energy_dashboard_compatible": data.get(
                "estimated_cumulative_energy_dashboard_compatible"
            ),
            "status_detail": data.get("estimated_cumulative_status_detail"),
            "last_successful_update": data.get("last_successful_update"),
        },
    ),
    YorkshireWaterSensorEntityDescription(
        key="yesterday_cost",
        translation_key="yesterday_cost",
        name="Yesterday Cost",
        icon="mdi:currency-gbp",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="GBP",
        value_fn=lambda data: data.get("yesterday_total_cost"),
        attrs_fn=lambda data: _cost_attrs(
            data,
            "yesterday_start",
            "yesterday_end",
            "yesterday",
        ),
    ),
    YorkshireWaterSensorEntityDescription(
        key="today_cost",
        translation_key="today_cost",
        name="Today Cost",
        icon="mdi:currency-gbp",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="GBP",
        value_fn=lambda data: data.get("today_total_cost"),
        attrs_fn=lambda data: _cost_attrs(
            data,
            "today_start",
            "today_end",
            "today",
        ),
    ),
    YorkshireWaterSensorEntityDescription(
        key="week_to_date_cost",
        translation_key="week_to_date_cost",
        name="Week to Date Cost",
        icon="mdi:currency-gbp",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="GBP",
        value_fn=lambda data: data.get("week_to_date_total_cost"),
        attrs_fn=lambda data: _cost_attrs(
            data,
            "week_start",
            "week_end",
            "week_to_date",
        ),
    ),
    YorkshireWaterSensorEntityDescription(
        key="previous_week_cost",
        translation_key="previous_week_cost",
        name="Previous Week Cost",
        icon="mdi:currency-gbp",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="GBP",
        value_fn=lambda data: data.get("previous_week_total_cost"),
        attrs_fn=lambda data: _cost_attrs(
            data,
            "previous_week_start",
            "previous_week_end",
            "previous_week",
        ),
    ),
    YorkshireWaterSensorEntityDescription(
        key="month_to_date_cost",
        translation_key="month_to_date_cost",
        name="Month to Date Cost",
        icon="mdi:currency-gbp",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="GBP",
        value_fn=lambda data: data.get("month_to_date_total_cost"),
        attrs_fn=lambda data: _cost_attrs(
            data,
            "month_start",
            "latest_data_date",
            "month_to_date",
        ),
    ),
    YorkshireWaterSensorEntityDescription(
        key="year_to_date_cost",
        translation_key="year_to_date_cost",
        name="Year to Date Cost",
        icon="mdi:currency-gbp",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="GBP",
        value_fn=lambda data: data.get("year_to_date_total_cost"),
        attrs_fn=lambda data: _cost_attrs(
            data,
            "year_start",
            "latest_data_date",
            "year_to_date",
        ),
    ),
    YorkshireWaterSensorEntityDescription(
        key="continuous_flow_alarm",
        translation_key="continuous_flow_alarm",
        name="Continuous Flow Alarm",
        icon="mdi:water-alert",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("continuous_flow_alarm"),
        attrs_fn=lambda data: {
            "latest_data_date": data.get("latest_data_date"),
            "latest_update_date": data.get("latest_update_date"),
            "last_successful_update": data.get("last_successful_update"),
        },
    ),
    YorkshireWaterSensorEntityDescription(
        key="data_latest_update_status",
        translation_key="data_latest_update_status",
        name="Data Latest Update Status",
        icon="mdi:database-clock",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("data_latest_update_status"),
        attrs_fn=lambda data: {
            "latest_data_date": data.get("latest_data_date"),
            "latest_update_date": data.get("latest_update_date"),
            "included_day_count": data.get("included_day_count"),
            "estimated_day_count": data.get("estimated_day_count"),
            "missing_day_count": data.get("missing_day_count"),
            "last_successful_update": data.get("last_successful_update"),
        },
    ),
    YorkshireWaterSensorEntityDescription(
        key="status",
        translation_key="status",
        name="Status",
        icon="mdi:cloud-check-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("status"),
        attrs_fn=lambda data: {
            "status_detail": data.get("status_detail"),
            "last_successful_update": data.get("last_successful_update"),
            "account_configured": bool(data.get("account_configured")),
            "meter_configured": bool(data.get("meter_configured")),
            "latest_data_date": data.get("latest_data_date"),
            "latest_update_date": data.get("latest_update_date"),
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Yorkshire Water sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities(
        YorkshireWaterSensor(coordinator, entry, description)
        for description in SENSORS
    )


class YorkshireWaterSensor(CoordinatorEntity[DataUpdateCoordinator], SensorEntity):
    """Yorkshire Water sensor entity."""

    entity_description: YorkshireWaterSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry: ConfigEntry,
        description: YorkshireWaterSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=DEFAULT_NAME,
            manufacturer="Yorkshire Water",
            model="Water Account",
        )

    @property
    def native_value(self) -> Any:
        """Return the sensor state."""
        data = self.coordinator.data or {}
        return self.entity_description.value_fn(data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.data or {}
        return self.entity_description.attrs_fn(data)
