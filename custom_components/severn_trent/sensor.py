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

    # FIXED: Changed from TOTAL to MEASUREMENT
    # Yesterday's usage is a fixed historical value, not cumulative
    _attr_state_class = SensorStateClass.MEASUREMENT
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

    # FIXED: Changed from TOTAL to MEASUREMENT
    # Weekly total is a rolling window calculation, not cumulative
    _attr_state_class = SensorStateClass.MEASUREMENT
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
        
        # Need both manual reading and usage data
        if not manual_data or not smart_data:
            return None
        
        latest_official = manual_data.get("latest_reading")
        official_date_str = manual_data.get("reading_date")
        
        if not latest_official or not official_date_str:
            return None
        
        # Parse the official reading date
        try:
            official_date_str_clean = official_date_str.split("T")[0] if "T" in official_date_str else official_date_str
            official_date = datetime.fromisoformat(official_date_str_clean).date()
        except (ValueError, AttributeError) as e:
            _LOGGER.error("Could not parse official reading date '%s': %s", official_date_str, e)
            return None
        
        _LOGGER.debug("Calculating estimated reading:")
        _LOGGER.debug("  Official reading: %s on %s", latest_official, official_date)
        
        # IMPROVED CALCULATION:
        # Use daily readings (all_readings) for more accurate estimation
        all_readings = smart_data.get("all_readings", [])
        
        if all_readings:
            # Use daily readings for precise calculation
            usage_since_official = 0
            days_counted = 0
            
            for reading in all_readings:
                reading_date_str = reading.get("date")
                reading_value = reading.get("usage", 0)
                
                if reading_date_str:
                    try:
                        reading_date_str_clean = reading_date_str.split("T")[0] if "T" in reading_date_str else reading_date_str
                        reading_date = datetime.fromisoformat(reading_date_str_clean).date()
                        
                        # Only include readings AFTER the official reading date
                        if reading_date > official_date:
                            usage_since_official += reading_value
                            days_counted += 1
                            _LOGGER.debug("  Daily reading: %s = %s m³ (included)", reading_date, reading_value)
                        else:
                            _LOGGER.debug("  Daily reading: %s = %s m³ (skipped - on or before official date)", reading_date, reading_value)
                    except (ValueError, AttributeError) as e:
                        _LOGGER.warning("Could not parse reading date '%s': %s", reading_date_str, e)
                        continue
            
            _LOGGER.debug("  Total usage since official (from %d daily readings): %s m³", days_counted, usage_since_official)
        else:
            # Fallback: use monthly readings if daily readings not available
            monthly_readings = smart_data.get("monthly_readings", [])
            usage_since_official = 0
            
            _LOGGER.debug("  No daily readings available, using monthly readings")
            
            for reading in monthly_readings:
                reading_date_str = reading.get("start_date")
                reading_value = reading.get("value", 0)
                
                if reading_date_str:
                    try:
                        reading_date_str_clean = reading_date_str.split("T")[0] if "T" in reading_date_str else reading_date_str
                        reading_date = datetime.fromisoformat(reading_date_str_clean).date()
                        
                        # Only include complete months that start AFTER the official reading
                        if reading_date > official_date:
                            usage_since_official += reading_value
                            _LOGGER.debug("  Monthly reading: %s = %s m³ (included)", reading_date, reading_value)
                        else:
                            _LOGGER.debug("  Monthly reading: %s = %s m³ (skipped)", reading_date, reading_value)
                    except (ValueError, AttributeError) as e:
                        _LOGGER.warning("Could not parse reading date '%s': %s", reading_date_str, e)
                        continue
            
            _LOGGER.debug("  Total usage since official (from monthly readings): %s m³", usage_since_official)
        
        estimated_current = latest_official + usage_since_official
        _LOGGER.debug("  Estimated current: %s m³", estimated_current)
        
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
        official_date_str = manual_data.get("reading_date")
        
        # Calculate usage since official reading
        usage_since_official = 0
        days_since_official = None
        days_counted = 0
        
        if official_date_str:
            try:
                official_date_str_clean = official_date_str.split("T")[0] if "T" in official_date_str else official_date_str
                official_date = datetime.fromisoformat(official_date_str_clean).date()
                
                # Try to use daily readings first
                all_readings = smart_data.get("all_readings", [])
                
                if all_readings:
                    for reading in all_readings:
                        reading_date_str = reading.get("date")
                        if reading_date_str:
                            try:
                                reading_date_str_clean = reading_date_str.split("T")[0] if "T" in reading_date_str else reading_date_str
                                reading_date = datetime.fromisoformat(reading_date_str_clean).date()
                                if reading_date > official_date:
                                    usage_since_official += reading.get("usage", 0)
                                    days_counted += 1
                            except (ValueError, AttributeError):
                                continue
                else:
                    # Fallback to monthly readings
                    monthly_readings = smart_data.get("monthly_readings", [])
                    for reading in monthly_readings:
                        reading_date_str = reading.get("start_date")
                        if reading_date_str:
                            try:
                                reading_date_str_clean = reading_date_str.split("T")[0] if "T" in reading_date_str else reading_date_str
                                reading_date = datetime.fromisoformat(reading_date_str_clean).date()
                                if reading_date > official_date:
                                    usage_since_official += reading.get("value", 0)
                            except (ValueError, AttributeError):
                                continue
                
                # Calculate days since official reading
                today = datetime.now().date()
                days_since_official = (today - official_date).days
            except (ValueError, AttributeError) as e:
                _LOGGER.error("Error calculating attributes: %s", e)
        
        attrs = {
            "last_official_reading": latest_official,
            "last_official_date": official_date_str,
            "usage_since_official": round(usage_since_official, 3) if usage_since_official else None,
            "days_since_official": days_since_official,
        }
        
        if days_counted > 0:
            attrs["daily_readings_used"] = days_counted
            attrs["estimation_note"] = "Official reading + daily usage totals (only days after official reading)"
        else:
            attrs["estimation_note"] = "Official reading + monthly usage totals (only complete months after official reading)"
        
        return attrs
