"""Sensor platform for Severn Trent Water integration."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.recorder.statistics import (
    statistics_during_period,
)

from .const import DOMAIN
from .coordinator import SevernTrentDataCoordinator

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
        SevernTrentPreviousDayUsageSensor(coordinator, account_number),
        SevernTrentWeekToDateSensor(coordinator, account_number),
        SevernTrentMonthToDateSensor(coordinator, account_number),
        SevernTrentOvernightUsageSensor(coordinator, account_number),
        SevernTrentOvernightLeakSensor(coordinator, account_number),
        SevernTrentMeterReadingSensor(coordinator, account_number),
        SevernTrentEstimatedMeterReadingSensor(coordinator, account_number),
    ]
    
    async_add_entities(sensors)


class SevernTrentPreviousDayUsageSensor(CoordinatorEntity, SensorEntity):
    """Sensor for previous day's total water usage."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_icon = "mdi:water"

    def __init__(
        self,
        coordinator: SevernTrentDataCoordinator,
        account_number: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._account_number = account_number
        self._attr_name = "Severn Trent Previous Day Usage"
        self._attr_unique_id = f"{account_number}_previous_day_usage"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data or "previous_day" not in self.coordinator.data:
            return None
        return self.coordinator.data["previous_day"].get("usage")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data or "previous_day" not in self.coordinator.data:
            return {}
        
        return {
            "date": self.coordinator.data["previous_day"].get("date"),
            "last_update": self.coordinator.data.get("last_successful_update"),
        }


class SevernTrentWeekToDateSensor(CoordinatorEntity, SensorEntity):
    """Sensor for current week's cumulative usage (Monday-Sunday)."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_icon = "mdi:calendar-week"

    def __init__(
        self,
        coordinator: SevernTrentDataCoordinator,
        account_number: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._account_number = account_number
        self._attr_name = "Severn Trent Week to Date"
        self._attr_unique_id = f"{account_number}_week_to_date"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data or "week_to_date" not in self.coordinator.data:
            return None
        return self.coordinator.data["week_to_date"].get("usage")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data or "week_to_date" not in self.coordinator.data:
            return {}
        
        week_data = self.coordinator.data["week_to_date"]
        start_date_str = week_data.get("start_date")
        
        # Calculate end date (Sunday)
        if start_date_str:
            start_date = datetime.fromisoformat(start_date_str).date()
            end_date = start_date + timedelta(days=6)
            end_date_str = end_date.isoformat()
        else:
            end_date_str = None
        
        return {
            "week_start": start_date_str,
            "week_end": end_date_str,
            "days_included": week_data.get("days_included", 0),
        }


class SevernTrentMonthToDateSensor(CoordinatorEntity, SensorEntity):
    """Sensor for current month's cumulative usage."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_icon = "mdi:calendar-month"

    def __init__(
        self,
        coordinator: SevernTrentDataCoordinator,
        account_number: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._account_number = account_number
        self._attr_name = "Severn Trent Month to Date"
        self._attr_unique_id = f"{account_number}_month_to_date"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data or "month_to_date" not in self.coordinator.data:
            return None
        return self.coordinator.data["month_to_date"].get("usage")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data or "month_to_date" not in self.coordinator.data:
            return {}
        
        return {
            "month": self.coordinator.data["month_to_date"].get("month"),
        }


class SevernTrentOvernightUsageSensor(CoordinatorEntity, SensorEntity):
    """Sensor for overnight usage (2am-5am) from previous day."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_icon = "mdi:weather-night"

    def __init__(
        self,
        coordinator: SevernTrentDataCoordinator,
        account_number: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._account_number = account_number
        self._attr_name = "Severn Trent Overnight Usage"
        self._attr_unique_id = f"{account_number}_overnight_usage"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        # Calculate overnight usage from hourly statistics (2am-5am)
        yesterday = (datetime.now() - timedelta(days=1)).date()
        
        # Query hourly statistics for yesterday between 2am-5am
        statistic_id = f"severn_trent:{self._account_number}:hourly_usage"
        
        start_time = datetime.combine(yesterday, datetime.min.time().replace(hour=2))
        end_time = datetime.combine(yesterday, datetime.min.time().replace(hour=6))
        
        try:
            stats = statistics_during_period(
                self.hass,
                start_time,
                end_time,
                {statistic_id},
                "hour",
                None,
                {"sum"}
            )
            
            if statistic_id in stats and stats[statistic_id]:
                # Sum all hourly values between 2am-5am
                total = sum(stat["sum"] for stat in stats[statistic_id] if stat.get("sum") is not None)
                return round(total, 3)
        except Exception as e:
            _LOGGER.warning("Could not calculate overnight usage: %s", e)
        
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        yesterday = (datetime.now() - timedelta(days=1)).date()
        return {
            "date": yesterday.isoformat(),
            "time_range": "02:00-05:59",
        }


class SevernTrentOvernightLeakSensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for detecting potential overnight leaks."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:pipe-leak"

    def __init__(
        self,
        coordinator: SevernTrentDataCoordinator,
        account_number: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._account_number = account_number
        self._attr_name = "Severn Trent Overnight Leak Alert"
        self._attr_unique_id = f"{account_number}_overnight_leak"
        self._threshold = 0.01  # 0.01 m³ threshold

    @property
    def is_on(self) -> bool | None:
        """Return true if leak detected."""
        # Get overnight usage from the other sensor
        yesterday = (datetime.now() - timedelta(days=1)).date()
        statistic_id = f"severn_trent:{self._account_number}:hourly_usage"
        
        start_time = datetime.combine(yesterday, datetime.min.time().replace(hour=2))
        end_time = datetime.combine(yesterday, datetime.min.time().replace(hour=6))
        
        try:
            stats = statistics_during_period(
                self.hass,
                start_time,
                end_time,
                {statistic_id},
                "hour",
                None,
                {"sum"}
            )
            
            if statistic_id in stats and stats[statistic_id]:
                total = sum(stat["sum"] for stat in stats[statistic_id] if stat.get("sum") is not None)
                return total > self._threshold
        except Exception as e:
            _LOGGER.warning("Could not check for overnight leak: %s", e)
        
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        yesterday = (datetime.now() - timedelta(days=1)).date()
        
        # Get actual overnight usage
        statistic_id = f"severn_trent:{self._account_number}:hourly_usage"
        start_time = datetime.combine(yesterday, datetime.min.time().replace(hour=2))
        end_time = datetime.combine(yesterday, datetime.min.time().replace(hour=6))
        
        overnight_usage = None
        try:
            stats = statistics_during_period(
                self.hass,
                start_time,
                end_time,
                {statistic_id},
                "hour",
                None,
                {"sum"}
            )
            
            if statistic_id in stats and stats[statistic_id]:
                total = sum(stat["sum"] for stat in stats[statistic_id] if stat.get("sum") is not None)
                overnight_usage = round(total, 3)
        except Exception as e:
            _LOGGER.warning("Could not get overnight usage: %s", e)
        
        return {
            "date": yesterday.isoformat(),
            "threshold": self._threshold,
            "overnight_usage": overnight_usage,
            "time_range": "02:00-05:59",
        }


class SevernTrentMeterReadingSensor(CoordinatorEntity, SensorEntity):
    """Sensor for manual meter reading (cumulative total)."""

    _attr_device_class = SensorDeviceClass.WATER
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_icon = "mdi:counter"

    def __init__(
        self,
        coordinator: SevernTrentDataCoordinator,
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
        coordinator: SevernTrentDataCoordinator,
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
        if not self.coordinator.data or "manual_meter" not in self.coordinator.data:
            return None
        
        manual_data = self.coordinator.data["manual_meter"]
        
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
        
        # Query daily statistics from official date until now
        statistic_id = f"severn_trent:{self._account_number}:daily_usage"
        
        start_time = datetime.combine(official_date + timedelta(days=1), datetime.min.time())
        end_time = datetime.now()
        
        usage_since_official = 0
        
        try:
            stats = statistics_during_period(
                self.hass,
                start_time,
                end_time,
                {statistic_id},
                "day",
                None,
                {"sum"}
            )
            
            if statistic_id in stats and stats[statistic_id]:
                usage_since_official = sum(stat["sum"] for stat in stats[statistic_id] if stat.get("sum") is not None)
        except Exception as e:
            _LOGGER.warning("Could not calculate estimated meter reading: %s", e)
            return latest_official
        
        estimated_current = latest_official + usage_since_official
        return round(estimated_current, 3)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data or "manual_meter" not in self.coordinator.data:
            return {}
        
        manual_data = self.coordinator.data["manual_meter"]
        
        latest_official = manual_data.get("latest_reading")
        official_date_str = manual_data.get("reading_date")
        
        if not official_date_str:
            return {}
        
        try:
            official_date_str_clean = official_date_str.split("T")[0] if "T" in official_date_str else official_date_str
            official_date = datetime.fromisoformat(official_date_str_clean).date()
            
            # Calculate days since official reading
            today = datetime.now().date()
            days_since_official = (today - official_date).days
            
            # Get usage since official from statistics
            statistic_id = f"severn_trent:{self._account_number}:daily_usage"
            start_time = datetime.combine(official_date + timedelta(days=1), datetime.min.time())
            end_time = datetime.now()
            
            usage_since_official = 0
            days_counted = 0
            
            try:
                stats = statistics_during_period(
                    self.hass,
                    start_time,
                    end_time,
                    {statistic_id},
                    "day",
                    None,
                    {"sum"}
                )
                
                if statistic_id in stats and stats[statistic_id]:
                    days_counted = len(stats[statistic_id])
                    usage_since_official = sum(stat["sum"] for stat in stats[statistic_id] if stat.get("sum") is not None)
            except Exception as e:
                _LOGGER.warning("Could not get usage for attributes: %s", e)
            
            return {
                "last_official_reading": latest_official,
                "last_official_date": official_date_str,
                "usage_since_official": round(usage_since_official, 3) if usage_since_official else None,
                "days_since_official": days_since_official,
                "daily_readings_used": days_counted,
                "estimation_note": "Official reading + daily usage totals from statistics"
            }
        except (ValueError, AttributeError) as e:
            _LOGGER.error("Error calculating attributes: %s", e)
            return {}
