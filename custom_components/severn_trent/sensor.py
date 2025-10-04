"""Sensor platform for Severn Trent Water integration."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Severn Trent sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    account_number = entry.data["account_number"]
    
    sensors = [
        SevernTrentYesterdayUsageSensor(coordinator, account_number),
        SevernTrentAverageDailyUsageSensor(coordinator, account_number),
        SevernTrentWeeklyTotalSensor(coordinator, account_number),
        SevernTrentMeterReadingSensor(coordinator, account_number),
        SevernTrentEstimatedMeterReadingSensor(coordinator, account_number),
    ]
    
    async_add_entities(sensors)

class SevernTrentYesterdayUsageSensor(CoordinatorEntity, SensorEntity):
    """Sensor for yesterday's water usage."""

    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:water"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        account_number: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._account_number = account_number
        self._attr_name = "Severn Trent Yesterday Usage"
        self._attr_unique_id = f"{account_number}_yesterday_usage"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data or "smart_meter" not in self.coordinator.data:
            return None
        return self.coordinator.data["smart_meter"].get("yesterday_usage")

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        if not self.coordinator.data or "smart_meter" not in self.coordinator.data:
            return UnitOfVolume.CUBIC_METERS
        return self.coordinator.data["smart_meter"].get("unit", UnitOfVolume.CUBIC_METERS)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data or "smart_meter" not in self.coordinator.data:
            return {}
        
        return {
            "date": self.coordinator.data["smart_meter"].get("yesterday_date"),
            "meter_id": self.coordinator.data["smart_meter"].get("meter_id"),
        }

class SevernTrentAverageDailyUsageSensor(CoordinatorEntity, SensorEntity):
    """Sensor for average daily water usage over the last 7 days."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:water-pump"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        account_number: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._account_number = account_number
        self._attr_name = "Severn Trent Daily Average"
        self._attr_unique_id = f"{account_number}_daily_average"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data or "smart_meter" not in self.coordinator.data:
            return None
        return self.coordinator.data["smart_meter"].get("daily_average")

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        if not self.coordinator.data or "smart_meter" not in self.coordinator.data:
            return UnitOfVolume.CUBIC_METERS
        unit = self.coordinator.data["smart_meter"].get("unit", UnitOfVolume.CUBIC_METERS)
        return f"{unit}/d"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data or "smart_meter" not in self.coordinator.data:
            return {}
        
        # Include recent readings for history
        all_readings = self.coordinator.data["smart_meter"].get("all_readings", [])
        
        return {
            "recent_readings": all_readings[:7] if all_readings else [],
            "period": "7 days",
        }

class SevernTrentWeeklyTotalSensor(CoordinatorEntity, SensorEntity):
    """Sensor for total water usage over the last 7 days."""

    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:water-outline"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        account_number: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._account_number = account_number
        self._attr_name = "Severn Trent Weekly Total"
        self._attr_unique_id = f"{account_number}_weekly_total"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data or "smart_meter" not in self.coordinator.data:
            return None
        return self.coordinator.data["smart_meter"].get("total_7day_usage")

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        if not self.coordinator.data or "smart_meter" not in self.coordinator.data:
            return UnitOfVolume.CUBIC_METERS
        return self.coordinator.data["smart_meter"].get("unit", UnitOfVolume.CUBIC_METERS)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data or "smart_meter" not in self.coordinator.data:
            return {}
        
        return {
            "period": "7 days",
            "days_included": len(self.coordinator.data["smart_meter"].get("all_readings", [])),
        }

class SevernTrentMeterReadingSensor(CoordinatorEntity, SensorEntity):
    """Sensor for manual meter reading (cumulative total)."""

    _attr_device_class = SensorDeviceClass.WATER
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_icon = "mdi:counter"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        account_number: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._account_number = account_number
        self._attr_name = "Severn Trent Meter Reading"
        self._attr_unique_id = f"{account_number}_meter_reading"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data or "manual_meter" not in self.coordinator.data:
            return None
        return self.coordinator.data["manual_meter"].get("latest_reading")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data or "manual_meter" not in self.coordinator.data:
            return {}
        
        manual_data = self.coordinator.data["manual_meter"]
        
        attrs = {
            "reading_date": manual_data.get("reading_date"),
            "reading_source": manual_data.get("reading_source"),
            "previous_reading": manual_data.get("previous_reading"),
            "previous_date": manual_data.get("previous_date"),
            "usage_since_last": manual_data.get("usage_since_last"),
            "days_since_last": manual_data.get("days_since_last"),
            "avg_daily_usage": manual_data.get("avg_daily_usage"),
        }
        
        # Add all historical readings
        all_readings = manual_data.get("all_readings", [])
        if all_readings:
            attrs["all_readings"] = all_readings
        
        return attrs

class SevernTrentEstimatedMeterReadingSensor(CoordinatorEntity, SensorEntity):
    """Sensor for estimated current meter reading based on official reading + daily usage."""

    _attr_device_class = SensorDeviceClass.WATER
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_icon = "mdi:gauge"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        account_number: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._account_number = account_number
        self._attr_name = "Severn Trent Estimated Meter Reading"
        self._attr_unique_id = f"{account_number}_estimated_meter_reading"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        
        manual_data = self.coordinator.data.get("manual_meter", {})
        smart_data = self.coordinator.data.get("smart_meter", {})
        
        # Need both manual reading and monthly usage data
        if not manual_data or not smart_data:
            return None
        
        latest_official = manual_data.get("latest_reading")
        official_date = manual_data.get("reading_date")
        monthly_readings = smart_data.get("monthly_readings", [])
        
        if not latest_official or not official_date:
            return None
        
        # Sum all monthly usage since the official reading date
        # Monthly data includes partial data for incomplete months
        usage_since_official = 0
        
        for reading in monthly_readings:
            reading_date = reading.get("start_date")
            if reading_date and reading_date > official_date:
                usage_since_official += reading.get("value", 0)
        
        estimated_current = latest_official + usage_since_official
        return round(estimated_current, 3)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {}
        
        manual_data = self.coordinator.data.get("manual_meter", {})
        smart_data = self.coordinator.data.get("smart_meter", {})
        
        if not manual_data or not smart_data:
            return {}
        
        latest_official = manual_data.get("latest_reading")
        official_date = manual_data.get("reading_date")
        monthly_readings = smart_data.get("monthly_readings", [])
        
        # Calculate usage since official reading
        usage_since_official = 0
        days_since_official = None
        
        if official_date:
            # Add all monthly usage since official reading
            for reading in monthly_readings:
                reading_date = reading.get("start_date")
                if reading_date and reading_date > official_date:
                    usage_since_official += reading.get("value", 0)
            
            # Calculate days since official reading
            from datetime import datetime
            official_dt = datetime.fromisoformat(official_date)
            today = datetime.now()
            days_since_official = (today - official_dt).days
        
        return {
            "last_official_reading": latest_official,
            "last_official_date": official_date,
            "usage_since_official": round(usage_since_official, 3) if usage_since_official else None,
            "days_since_official": days_since_official,
            "monthly_periods_included": len([r for r in monthly_readings if r.get("start_date", "") > (official_date or "")]),
            "estimation_note": "Official reading + monthly usage totals (includes partial current month)"
        }
