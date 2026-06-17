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

from .const import CONF_ACCOUNT_ID, CONF_METER_ID, DEFAULT_NAME, DOMAIN


@dataclass(frozen=True, kw_only=True)
class YorkshireWaterSensorEntityDescription(SensorEntityDescription):
    """Description for Yorkshire Water sensors."""

    value_fn: Callable[[dict[str, Any]], Any] = lambda data: None
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] = lambda data: {}


def _period_attrs(
    data: dict[str, Any],
    start_key: str,
    end_key: str,
    raw_period_key: str | None = None,
) -> dict[str, Any]:
    """Build common source period attributes."""
    attrs: dict[str, Any] = {
        "source_period_start": data.get(start_key),
        "source_period_end": data.get(end_key),
        "unit": UnitOfVolume.CUBIC_METERS,
        "last_successful_update": data.get("last_successful_update"),
    }
    if raw_period_key:
        attrs["source_periods"] = data.get(raw_period_key) or []
    return attrs


SENSORS: tuple[YorkshireWaterSensorEntityDescription, ...] = (
    YorkshireWaterSensorEntityDescription(
        key="yesterday_usage",
        translation_key="yesterday_usage",
        name="Yesterday Usage",
        icon="mdi:water",
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        value_fn=lambda data: data.get("yesterday_usage_m3"),
        attrs_fn=lambda data: _period_attrs(data, "yesterday_start", "yesterday_end"),
    ),
    YorkshireWaterSensorEntityDescription(
        key="today_usage",
        translation_key="today_usage",
        name="Today Usage",
        icon="mdi:water-outline",
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        value_fn=lambda data: data.get("today_usage_m3"),
        attrs_fn=lambda data: _period_attrs(data, "today_start", "today_end"),
    ),
    YorkshireWaterSensorEntityDescription(
        key="daily_average",
        translation_key="daily_average",
        name="7-Day Average",
        icon="mdi:water-percent",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        value_fn=lambda data: data.get("daily_average_m3"),
        attrs_fn=lambda data: _period_attrs(
            data,
            "daily_average_period_start",
            "daily_average_period_end",
            "daily_periods",
        ),
    ),
    YorkshireWaterSensorEntityDescription(
        key="week_to_date",
        translation_key="week_to_date",
        name="Week to Date",
        icon="mdi:water-sync",
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        value_fn=lambda data: data.get("week_to_date_m3"),
        attrs_fn=lambda data: {
            "source_period_start": data.get("week_start"),
            "source_period_end": datetime.now().date().isoformat(),
            "unit": UnitOfVolume.CUBIC_METERS,
            "last_successful_update": data.get("last_successful_update"),
        },
    ),
    YorkshireWaterSensorEntityDescription(
        key="previous_week",
        translation_key="previous_week",
        name="Previous Week",
        icon="mdi:water-check",
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        value_fn=lambda data: data.get("previous_week_m3"),
        attrs_fn=lambda data: _period_attrs(
            data,
            "previous_week_start",
            "previous_week_end",
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
            "raw_unit": UnitOfVolume.CUBIC_METERS,
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
            "account_configured": bool(data.get("account_id")),
            "meter_configured": bool(data.get("meter_id")),
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
    account_or_meter = (
        entry.data.get(CONF_METER_ID)
        or entry.data.get(CONF_ACCOUNT_ID)
        or entry.entry_id
    )

    async_add_entities(
        YorkshireWaterSensor(coordinator, entry, account_or_meter, description)
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
        account_or_meter: str,
        description: YorkshireWaterSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{account_or_meter}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=DEFAULT_NAME,
            manufacturer="Yorkshire Water",
            model="Water Account",
            serial_number=entry.data.get(CONF_METER_ID),
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
