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
        SevernTrentWeekToDateSensor(coordinator, account_number),
        SevernTrentPreviousWeekSensor(coordinator, account_number),
        SevernTrentMeterReadingSensor(coordinator, account_number),
        SevernTrentEstimatedMeterReadingSensor(coordinator, account_number),
    ]

    async_add_entities(sensors)

class SevernTrentYesterdayUsageSensor(CoordinatorEntity, SensorEntity):
    """Sensor for yesterday's water usage."""

    _attr_device_class = SensorDeviceClass.WATER
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
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

    _attr_device_class = SensorDeviceClass.WATER
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
        return UnitOfVolume.CUBIC_METERS

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

class SevernTrentWeekToDateSensor(CoordinatorEntity, SensorEntity):
    """Sensor for water usage from Monday to present in current week."""

    _attr_device_class = SensorDeviceClass.WATER
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_icon = "mdi:water-outline"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
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
        if not self.coordinator.data or "smart_meter" not in self.coordinator.data:
            return None
        return self.coordinator.data["smart_meter"].get("week_to_date_usage")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data or "smart_meter" not in self.coordinator.data:
            return {}

        smart_data = self.coordinator.data["smart_meter"]
        return {
            "week_start": smart_data.get("week_start_date"),
            "days_in_week": smart_data.get("days_in_current_week"),
        }


class SevernTrentPreviousWeekSensor(CoordinatorEntity, SensorEntity):
    """Sensor for water usage for the previous week (Monday-Sunday)."""

    _attr_device_class = SensorDeviceClass.WATER
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_icon = "mdi:water-check-outline"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        account_number: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._account_number = account_number
        self._attr_name = "Severn Trent Previous Week"
        self._attr_unique_id = f"{account_number}_previous_week"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data or "smart_meter" not in self.coordinator.data:
            return None
        return self.coordinator.data["smart_meter"].get("previous_week_usage")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data or "smart_meter" not in self.coordinator.data:
            return {}

        smart_data = self.coordinator.data["smart_meter"]
        return {
            "week_start": smart_data.get("previous_week_start_date"),
            "week_end": smart_data.get("previous_week_end_date"),
            "days_in_week": 7,
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
        official_date = manual_data.get("reading_date")
        monthly_readings = smart_data.get("monthly_readings", [])
        daily_readings = smart_data.get("daily_readings_since_official", [])

        if not latest_official or not official_date:
            return None

        _LOGGER.debug("Calculating estimated reading:")
        _LOGGER.debug("  Official reading: %s on %s", latest_official, official_date)
        _LOGGER.debug("  Monthly readings available: %d", len(monthly_readings))
        _LOGGER.debug("  Daily readings available: %d", len(daily_readings))

        # Parse official date once
        try:
            official_date_str = official_date.split("T")[0] if "T" in official_date else official_date
            official_dt = datetime.fromisoformat(official_date_str)
        except (ValueError, AttributeError) as e:
            _LOGGER.error("Invalid official date format: %s - %s", official_date, e)
            return None

        usage_since_official = 0

        # Add daily usage from partial month (if provided by API)
        for reading in daily_readings:
            usage_since_official += reading.get("value", 0)
            _LOGGER.debug("  Daily reading: %s = %s m³", reading.get("date"), reading.get("value", 0))

        # Add monthly usage (complete months after the official reading)
        # Monthly readings have start_date as first of the month
        #
        # Key insight: Only include monthly readings that occur AFTER the official reading date
        # This ensures we never include historical data from before the official reading
        official_month_start = official_dt.replace(day=1)

        # Check if official reading was on the 1st of the month
        is_first_of_month = (official_dt.day == 1)

        for reading in monthly_readings:
            reading_date = reading.get("start_date")
            reading_value = reading.get("value", 0)

            if reading_date:
                try:
                    reading_date_str = reading_date.split("T")[0] if "T" in reading_date else reading_date
                    reading_dt = datetime.fromisoformat(reading_date_str)

                    # CRITICAL: Always compare against the actual official reading date, not just month boundary
                    # This prevents including any months before the official reading
                    if is_first_of_month:
                        # Reading on 1st: include months from that date onwards
                        should_include = reading_dt >= official_dt
                    else:
                        # Reading mid-month: exclude that month (covered by daily data)
                        should_include = reading_dt > official_month_start

                    if should_include:
                        _LOGGER.debug("  Monthly reading: %s = %s m³ (included)", reading_date_str, reading_value)
                        usage_since_official += reading_value
                    else:
                        _LOGGER.debug("  Monthly reading: %s = %s m³ (skipped - before official reading)", reading_date_str, reading_value)
                except (ValueError, AttributeError) as e:
                    _LOGGER.warning("Invalid reading date format: %s - %s", reading_date, e)
                    continue

        estimated_current = latest_official + usage_since_official
        _LOGGER.debug("  Total usage since official: %s m³", usage_since_official)
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
        official_date = manual_data.get("reading_date")
        monthly_readings = smart_data.get("monthly_readings", [])
        daily_readings = smart_data.get("daily_readings_since_official", [])

        # Calculate usage since official reading
        usage_since_official = 0
        days_since_official = None
        monthly_periods_included = 0

        if official_date:
            try:
                official_date_str = official_date.split("T")[0] if "T" in official_date else official_date
                official_dt = datetime.fromisoformat(official_date_str)
                official_month_start = official_dt.replace(day=1)
                is_first_of_month = (official_dt.day == 1)

                # Add daily usage
                for reading in daily_readings:
                    usage_since_official += reading.get("value", 0)

                # Add monthly usage (complete months after official reading)
                for reading in monthly_readings:
                    reading_date = reading.get("start_date")
                    if reading_date:
                        try:
                            reading_date_str = reading_date.split("T")[0] if "T" in reading_date else reading_date
                            reading_dt = datetime.fromisoformat(reading_date_str)

                            # Include months based on official reading day
                            if is_first_of_month:
                                # Compare against actual official date to prevent including prior months
                                should_include = reading_dt >= official_dt
                            else:
                                should_include = reading_dt > official_month_start

                            if should_include:
                                usage_since_official += reading.get("value", 0)
                                monthly_periods_included += 1
                        except (ValueError, AttributeError):
                            continue

                # Calculate days since official reading
                today = datetime.now()
                days_since_official = (today - official_dt).days
            except (ValueError, AttributeError) as e:
                _LOGGER.warning("Error calculating attributes: %s", e)

        return {
            "last_official_reading": latest_official,
            "last_official_date": official_date,
            "usage_since_official": round(usage_since_official, 3) if usage_since_official else None,
            "days_since_official": days_since_official,
            "daily_periods_included": len(daily_readings),
            "monthly_periods_included": monthly_periods_included,
            "estimation_note": "Official reading + daily usage (partial month) + monthly totals (complete months)"
        }
