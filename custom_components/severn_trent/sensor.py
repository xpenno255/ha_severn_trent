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
from homeassistant.const import EntityCategory, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
)

from .const import DOMAIN
from .api import WATER_TIME_ZONE

_LOGGER = logging.getLogger(__name__)

class SevernTrentBaseSensor(SensorEntity):
    """Base sensor with device info."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        account_number: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__()
        self.coordinator = coordinator
        self._account_number = account_number

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._account_number)},
            name=f"Severn Trent Water ({self._account_number})",
            manufacturer="Severn Trent",
            model="Water Meter",
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.coordinator.async_add_listener(self._handle_coordinator_update))
        self._handle_coordinator_update()

    def _meter_id(self) -> str | None:
        if not self.coordinator.data:
            return None

        smart_meter = self.coordinator.data.get("smart_meter", {}) or {}
        manual_meter = self.coordinator.data.get("manual_meter", {}) or {}
        return smart_meter.get("meter_id") or manual_meter.get("meter_id")

    def _handle_coordinator_update(self) -> None:
        meter_id = self._meter_id()
        if meter_id and self._attr_device_info:
            self._attr_device_info["serial_number"] = meter_id
        self._attr_available = self.coordinator.last_update_success and self._attr_native_value is not None
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Route manual entity refreshes through the shared coordinator."""
        await self.coordinator.async_request_refresh()

    def _set_period_reset(self, period_start: str | None) -> None:
        """Identify a consumption period even when successive totals are equal."""
        if self._attr_native_value is None:
            return
        try:
            self._attr_last_reset = datetime.fromisoformat(period_start).replace(
                tzinfo=WATER_TIME_ZONE
            )
        except (TypeError, ValueError):
            # Never publish a period total with an unknown reset boundary.
            self._attr_native_value = None

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
        SevernTrentBalanceSensor(coordinator, account_number),
        SevernTrentOverdueBalanceSensor(coordinator, account_number),
        SevernTrentRateLimitRemainingSensor(coordinator, account_number),
        SevernTrentMarketSupplyPointIdSensor(coordinator, account_number),
        SevernTrentDeviceIdSensor(coordinator, account_number),
        SevernTrentCapabilityTypeSensor(coordinator, account_number),
        SevernTrentPaymentAmountSensor(coordinator, account_number),
        SevernTrentMeterDigitsSensor(coordinator, account_number),
        SevernTrentLatestManualReadingMetaSensor(coordinator, account_number),
        SevernTrentOutstandingPaymentSensor(coordinator, account_number),
        SevernTrentNextPaymentAmountSensor(coordinator, account_number),
        SevernTrentNextPaymentDateSensor(coordinator, account_number),
        SevernTrentSmartMeterStatusSensor(coordinator, account_number),
        SevernTrentLatestDailySensor(coordinator, account_number),
        SevernTrentHistorySensor(coordinator, account_number),
        SevernTrentUsagePatternSensor(coordinator, account_number),
    ]

    async_add_entities(sensors)


class SevernTrentBalanceSensor(SevernTrentBaseSensor):
    """Sensor for current account balance."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "GBP"
    _attr_icon = "mdi:currency-gbp"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        account_number: str,
    ) -> None:
        super().__init__(coordinator, account_number)
        self._attr_name = "Balance"
        self._attr_unique_id = f"{account_number}_balance"

    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data or {}
        balance = data.get("balance") or {}
        self._attr_native_value = balance.get("balance_gbp")
        attrs: dict[str, Any] = {}
        value = balance.get("balance_gbp")
        if value is not None:
            attrs["balance_status"] = "credit" if value > 0 else "debit" if value < 0 else "settled"
            attrs["credit_gbp"] = max(value, 0)
            attrs["amount_owed_gbp"] = max(-value, 0)
        if "balance_pence" in balance:
            attrs["balance_pence"] = balance.get("balance_pence")
        if "overdue_balance_gbp" in balance and balance.get("overdue_balance_gbp") is not None:
            attrs["overdue_balance_gbp"] = balance.get("overdue_balance_gbp")
        if "overdue_balance_pence" in balance and balance.get("overdue_balance_pence") is not None:
            attrs["overdue_balance_pence"] = balance.get("overdue_balance_pence")
        self._attr_extra_state_attributes = attrs
        super()._handle_coordinator_update()


class SevernTrentOverdueBalanceSensor(SevernTrentBaseSensor):
    """Sensor for overdue account balance."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "GBP"
    _attr_icon = "mdi:cash-alert"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        account_number: str,
    ) -> None:
        super().__init__(coordinator, account_number)
        self._attr_name = "Overdue Balance"
        self._attr_unique_id = f"{account_number}_overdue_balance"

    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data or {}
        balance = data.get("balance") or {}
        self._attr_native_value = balance.get("overdue_balance_gbp")
        self._attr_extra_state_attributes = {
            "overdue_balance_pence": balance.get("overdue_balance_pence"),
        }
        super()._handle_coordinator_update()


class SevernTrentYesterdayUsageSensor(SevernTrentBaseSensor):
    """Sensor for yesterday's water usage."""

    _attr_device_class = SensorDeviceClass.WATER
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_icon = "mdi:water"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        account_number: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, account_number)
        self._attr_name = "Yesterday Usage"
        self._attr_unique_id = f"{account_number}_yesterday_usage"

    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data or {}
        smart = data.get("smart_meter") or {}
        self._attr_native_value = smart.get("yesterday_usage")
        self._set_period_reset(smart.get("yesterday_date"))
        self._attr_extra_state_attributes = {
            "date": smart.get("yesterday_date"),
            "meter_id": smart.get("meter_id"),
        }
        super()._handle_coordinator_update()

class SevernTrentAverageDailyUsageSensor(SevernTrentBaseSensor):
    """Sensor for average daily water usage over the last 7 days."""

    _attr_device_class = SensorDeviceClass.WATER
    _attr_icon = "mdi:water-pump"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        account_number: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, account_number)
        self._attr_name = "Daily Average"
        self._attr_unique_id = f"{account_number}_daily_average"

        self._attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS

    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data or {}
        smart = data.get("smart_meter") or {}
        self._attr_native_value = smart.get("daily_average")
        self._attr_extra_state_attributes = {
            "recent_readings": smart.get("recent_readings", []),
            "days_received": smart.get("days_in_average", 0),
            "days_expected": 7,
            "period": "7 days",
        }
        super()._handle_coordinator_update()

class SevernTrentWeekToDateSensor(SevernTrentBaseSensor):
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
        super().__init__(coordinator, account_number)
        self._attr_name = "Week to Date"
        self._attr_unique_id = f"{account_number}_week_to_date"

    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data or {}
        smart = data.get("smart_meter") or {}
        self._attr_native_value = smart.get("week_to_date_usage")
        self._set_period_reset(smart.get("week_start_date"))
        self._attr_extra_state_attributes = {
            "week_start": smart.get("week_start_date"),
            "days_in_week": smart.get("days_in_current_week"),
            "days_expected": smart.get("days_expected_current_week"),
        }
        super()._handle_coordinator_update()


class SevernTrentPreviousWeekSensor(SevernTrentBaseSensor):
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
        super().__init__(coordinator, account_number)
        self._attr_name = "Previous Week"
        self._attr_unique_id = f"{account_number}_previous_week"

    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data or {}
        smart = data.get("smart_meter") or {}
        self._attr_native_value = smart.get("previous_week_usage")
        self._set_period_reset(smart.get("previous_week_start_date"))
        self._attr_extra_state_attributes = {
            "week_start": smart.get("previous_week_start_date"),
            "week_end": smart.get("previous_week_end_date"),
            "days_in_week": 7,
            "days_received": smart.get("days_in_previous_week"),
        }
        super()._handle_coordinator_update()

class SevernTrentMeterReadingSensor(SevernTrentBaseSensor):
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
        super().__init__(coordinator, account_number)
        self._attr_name = "Meter Reading"
        self._attr_unique_id = f"{account_number}_meter_reading"

    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data or {}
        manual = data.get("manual_meter") or {}
        self._attr_native_value = manual.get("latest_reading")

        attrs: dict[str, Any] = {
            "reading_date": manual.get("reading_date"),
            "reading_source": manual.get("reading_source"),
            "previous_reading": manual.get("previous_reading"),
            "previous_date": manual.get("previous_date"),
            "usage_since_last": manual.get("usage_since_last"),
            "days_since_last": manual.get("days_since_last"),
            "avg_daily_usage": manual.get("avg_daily_usage"),
        }
        all_readings = manual.get("all_readings", [])
        if all_readings:
            attrs["all_readings"] = all_readings

        self._attr_extra_state_attributes = attrs
        super()._handle_coordinator_update()

class SevernTrentEstimatedMeterReadingSensor(SevernTrentBaseSensor):
    """Sensor for estimated current meter reading based on official reading + daily usage."""

    _attr_device_class = SensorDeviceClass.WATER
    # Estimates can be corrected downwards; that is not a physical meter reset.
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_icon = "mdi:gauge"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        account_number: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, account_number)
        self._attr_name = "Estimated Meter Reading"
        self._attr_unique_id = f"{account_number}_estimated_meter_reading"

    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data or {}
        manual_data = data.get("manual_meter") or {}
        smart_data = data.get("smart_meter") or {}

        latest_official = manual_data.get("latest_reading")
        official_date = manual_data.get("reading_date")
        monthly_readings = smart_data.get("monthly_readings") or []
        daily_readings = smart_data.get("daily_readings_since_official") or []

        if latest_official is None or not official_date:
            self._attr_native_value = None
            self._attr_extra_state_attributes = {}
            super()._handle_coordinator_update()
            return

        try:
            official_date_str = official_date.split("T")[0] if "T" in official_date else official_date
            official_dt = datetime.fromisoformat(official_date_str)
        except (ValueError, AttributeError) as e:
            _LOGGER.error("Invalid official date format: %s - %s", official_date, e)
            self._attr_native_value = None
            self._attr_extra_state_attributes = {
                "last_official_reading": latest_official,
                "last_official_date": official_date,
            }
            super()._handle_coordinator_update()
            return

        today = datetime.now(WATER_TIME_ZONE).date()
        official_day = official_dt.date()
        if official_day > today:
            self._attr_native_value = None
            self._attr_extra_state_attributes = {"reason": "Official reading date is in the future"}
            super()._handle_coordinator_update()
            return

        if official_dt.month == 12:
            next_month = official_dt.replace(year=official_dt.year + 1, month=1, day=1)
        else:
            next_month = official_dt.replace(month=official_dt.month + 1, day=1)

        # Require each daily interval in the initial partial month and each
        # following monthly interval. An absent period is not zero consumption.
        daily_by_date = {r.get("date"): r.get("value") for r in daily_readings}
        monthly_by_date = {r.get("start_date"): r.get("value") for r in monthly_readings}
        missing_periods = []
        included_daily = []
        included_monthly = []
        if official_dt.day != 1:
            day = official_day
            while day < min(next_month.date(), today):
                value = daily_by_date.get(day.isoformat())
                if value is None:
                    missing_periods.append(day.isoformat())
                else:
                    included_daily.append(value)
                day += timedelta(days=1)
            month = next_month.date()
        else:
            month = official_day
        while month < today:
            value = monthly_by_date.get(month.isoformat())
            if value is None:
                missing_periods.append(month.isoformat())
            else:
                included_monthly.append(value)
            month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)

        if missing_periods:
            self._attr_native_value = None
            self._attr_extra_state_attributes = {
                "last_official_reading": latest_official,
                "last_official_date": official_date,
                "missing_periods": missing_periods,
                "reason": "Usage history does not cover the period since the official reading",
            }
            super()._handle_coordinator_update()
            return

        usage_since_official = sum(included_daily) + sum(included_monthly)
        monthly_periods_included = len(included_monthly)

        estimated_current = latest_official + usage_since_official
        self._attr_native_value = round(estimated_current, 3)

        days_since_official = (today - official_day).days
        self._attr_extra_state_attributes = {
            "last_official_reading": latest_official,
            "last_official_date": official_date,
            "usage_since_official": round(usage_since_official, 3),
            "days_since_official": days_since_official,
            "daily_periods_included": len(included_daily),
            "monthly_periods_included": monthly_periods_included,
            "estimation_note": "Official reading + available usage; current month may contain delayed or partial readings",
        }
        super()._handle_coordinator_update()


class SevernTrentRateLimitRemainingSensor(SevernTrentBaseSensor):
    """Diagnostic sensor for API rate limit remaining points."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:api"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        account_number: str,
    ) -> None:
        super().__init__(coordinator, account_number)
        self._attr_name = "API Rate Limit Remaining"
        self._attr_unique_id = f"{account_number}_api_rate_limit_remaining"
        self._attr_native_unit_of_measurement = "points"

    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data or {}
        rate = data.get("rate_limit") or {}
        self._attr_native_value = rate.get("remaining_points")
        self._attr_extra_state_attributes = {
            "is_blocked": rate.get("is_blocked"),
            "limit": rate.get("limit"),
            "remaining_points": rate.get("remaining_points"),
            "used_points": rate.get("used_points"),
            "ttl": rate.get("ttl"),
        }
        super()._handle_coordinator_update()


class _SevernTrentMeterInfoBase(SevernTrentBaseSensor):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = None

    def _meter_info(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        return data.get("meter_info") or {}


class SevernTrentMarketSupplyPointIdSensor(_SevernTrentMeterInfoBase):
    _attr_icon = "mdi:identifier"

    def __init__(self, coordinator: DataUpdateCoordinator, account_number: str) -> None:
        super().__init__(coordinator, account_number)
        self._attr_name = "Market Supply Point ID"
        self._attr_unique_id = f"{account_number}_market_supply_point_id"

    def _handle_coordinator_update(self) -> None:
        info = self._meter_info()
        self._attr_native_value = info.get("market_supply_point_id")
        self._attr_extra_state_attributes = {}
        super()._handle_coordinator_update()


class SevernTrentDeviceIdSensor(_SevernTrentMeterInfoBase):
    _attr_icon = "mdi:barcode"

    def __init__(self, coordinator: DataUpdateCoordinator, account_number: str) -> None:
        super().__init__(coordinator, account_number)
        self._attr_name = "Device ID"
        self._attr_unique_id = f"{account_number}_device_id"

    def _handle_coordinator_update(self) -> None:
        info = self._meter_info()
        self._attr_native_value = info.get("device_id")
        self._attr_extra_state_attributes = {}
        super()._handle_coordinator_update()


class SevernTrentCapabilityTypeSensor(_SevernTrentMeterInfoBase):
    _attr_icon = "mdi:meter-electric-outline"

    def __init__(self, coordinator: DataUpdateCoordinator, account_number: str) -> None:
        super().__init__(coordinator, account_number)
        self._attr_name = "Meter Capability"
        self._attr_unique_id = f"{account_number}_capability_type"

    def _handle_coordinator_update(self) -> None:
        info = self._meter_info()
        self._attr_native_value = info.get("capability_type")
        self._attr_extra_state_attributes = {}
        super()._handle_coordinator_update()


class SevernTrentPaymentAmountSensor(SevernTrentBaseSensor):
    """Sensor for the current active payment amount (e.g. direct debit)."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "GBP"
    _attr_icon = "mdi:cash-sync"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        account_number: str,
    ) -> None:
        super().__init__(coordinator, account_number)
        self._attr_name = "Payment Amount"
        self._attr_unique_id = f"{account_number}_payment_amount"

    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data or {}
        schedule = data.get("payment_schedule") or {}

        self._attr_native_value = schedule.get("payment_amount_gbp")
        self._attr_extra_state_attributes = {
            "schedule_id": schedule.get("id"),
            "payment_amount_pence": schedule.get("payment_amount_pence"),
            "payment_day": schedule.get("payment_day"),
            "payment_frequency": schedule.get("payment_frequency"),
            "payment_frequency_multiplier": schedule.get("payment_frequency_multiplier"),
            "is_variable_payment_amount": schedule.get("is_variable_payment_amount"),
            "valid_to": schedule.get("valid_to"),
            "schedule_type": schedule.get("schedule_type"),
        }
        super()._handle_coordinator_update()


class _SevernTrentMeterDetailsBase(SevernTrentBaseSensor):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = None

    def _meter_details(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        return data.get("meter_details") or {}


class SevernTrentMeterDigitsSensor(_SevernTrentMeterDetailsBase):
    _attr_icon = "mdi:numeric"

    def __init__(self, coordinator: DataUpdateCoordinator, account_number: str) -> None:
        super().__init__(coordinator, account_number)
        self._attr_name = "Meter Digits"
        self._attr_unique_id = f"{account_number}_meter_digits"

    def _handle_coordinator_update(self) -> None:
        details = self._meter_details()
        self._attr_native_value = details.get("number_of_digits")
        self._attr_extra_state_attributes = {
            "meter_internal_id": details.get("meter_internal_id"),
            "serial_number": details.get("serial_number"),
        }
        super()._handle_coordinator_update()


class SevernTrentLatestManualReadingMetaSensor(_SevernTrentMeterDetailsBase):
    _attr_icon = "mdi:card-text-outline"

    def __init__(self, coordinator: DataUpdateCoordinator, account_number: str) -> None:
        super().__init__(coordinator, account_number)
        self._attr_name = "Latest Reading Meta"
        self._attr_unique_id = f"{account_number}_latest_reading_meta"

    def _handle_coordinator_update(self) -> None:
        details = self._meter_details()
        # Use latest reading id as the state so it is stable and visible.
        self._attr_native_value = details.get("latest_reading_id")
        self._attr_extra_state_attributes = {
            "latest_reading": details.get("latest_reading"),
            "latest_reading_raw": details.get("latest_reading_raw"),
            "latest_reading_date": details.get("latest_reading_date"),
            "latest_reading_source": details.get("latest_reading_source"),
            "latest_reading_is_held": details.get("latest_reading_is_held"),
            "meter_internal_id": details.get("meter_internal_id"),
            "serial_number": details.get("serial_number"),
        }
        super()._handle_coordinator_update()


class SevernTrentOutstandingPaymentSensor(SevernTrentBaseSensor):
    """Sensor for outstanding payments."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "GBP"
    _attr_icon = "mdi:cash-alert"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        account_number: str,
    ) -> None:
        super().__init__(coordinator, account_number)
        self._attr_name = "Outstanding Payment"
        self._attr_unique_id = f"{account_number}_outstanding_payment"

    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data or {}
        outstanding = data.get("outstanding_payment") or {}
        self._attr_native_value = outstanding.get("payments_outstanding_gbp")
        self._attr_extra_state_attributes = {
            "payments_outstanding_pence": outstanding.get("payments_outstanding_pence"),
        }
        super()._handle_coordinator_update()


class _SevernTrentNextPaymentBase(SevernTrentBaseSensor):
    def _next_payment(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        return data.get("next_payment") or {}


class SevernTrentNextPaymentAmountSensor(_SevernTrentNextPaymentBase):
    """Sensor for the next upcoming payment amount."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "GBP"
    _attr_icon = "mdi:calendar-cash"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        account_number: str,
    ) -> None:
        super().__init__(coordinator, account_number)
        self._attr_name = "Next Payment Amount"
        self._attr_unique_id = f"{account_number}_next_payment_amount"

    def _handle_coordinator_update(self) -> None:
        nxt = self._next_payment()
        self._attr_native_value = nxt.get("amount_gbp")
        self._attr_extra_state_attributes = {
            "amount_pence": nxt.get("amount_pence"),
            "date": nxt.get("date"),
            "ledger_number": nxt.get("ledger_number"),
        }
        super()._handle_coordinator_update()


class SevernTrentNextPaymentDateSensor(_SevernTrentNextPaymentBase):
    """Sensor for the next upcoming payment date."""

    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:calendar"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        account_number: str,
    ) -> None:
        super().__init__(coordinator, account_number)
        self._attr_name = "Next Payment Date"
        self._attr_unique_id = f"{account_number}_next_payment_date"

    def _handle_coordinator_update(self) -> None:
        nxt = self._next_payment()
        date_str = nxt.get("date")
        if isinstance(date_str, str) and date_str:
            try:
                self._attr_native_value = datetime.fromisoformat(date_str).date()
            except ValueError:
                self._attr_native_value = None
        else:
            self._attr_native_value = None

        self._attr_extra_state_attributes = {
            "amount_gbp": nxt.get("amount_gbp"),
            "amount_pence": nxt.get("amount_pence"),
            "ledger_number": nxt.get("ledger_number"),
        }
        super()._handle_coordinator_update()


class SevernTrentSmartMeterStatusSensor(SevernTrentBaseSensor):
    """Diagnostic sensor showing smart meter data availability status."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:wifi"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        account_number: str,
    ) -> None:
        super().__init__(coordinator, account_number)
        self._attr_name = "Smart Meter Status"
        self._attr_unique_id = f"{account_number}_smart_meter_status"

    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data or {}
        smart = data.get("smart_meter") or {}
        manual = data.get("manual_meter") or {}

        if not smart and not manual:
            self._attr_native_value = "error"
            self._attr_extra_state_attributes = {
                "smart_meter_data": False,
                "manual_meter_data": False,
                "reason": "No data returned from API",
            }
        elif not smart:
            self._attr_native_value = "manual_only"
            self._attr_extra_state_attributes = {
                "smart_meter_data": False,
                "manual_meter_data": bool(manual),
                "reason": "Smart meter readings unavailable; only manual readings returned",
                "meter_id": manual.get("meter_id"),
            }
        else:
            yesterday = smart.get("yesterday_usage")
            daily_avg = smart.get("daily_average")
            wtd = smart.get("week_to_date_usage")
            prev_week = smart.get("previous_week_usage")
            has_daily_data = bool(smart.get("all_readings"))
            if not has_daily_data:
                self._attr_native_value = "no_daily_data"
            elif yesterday is None:
                self._attr_native_value = "stale_data"
            elif daily_avg is None or wtd is None or prev_week is None:
                self._attr_native_value = "incomplete_data"
            else:
                self._attr_native_value = "ok"
            self._attr_extra_state_attributes = {
                "smart_meter_data": True,
                "manual_meter_data": bool(manual),
                "has_daily_readings": has_daily_data,
                "latest_daily_date": smart.get("latest_daily_date"),
                "days_in_average": smart.get("days_in_average", 0),
                "days_in_previous_week": smart.get("days_in_previous_week", 0),
                "yesterday_usage": yesterday,
                "daily_average": daily_avg,
                "week_to_date_usage": wtd,
                "previous_week_usage": prev_week,
                "meter_id": smart.get("meter_id"),
                "monthly_readings_count": len(smart.get("monthly_readings", [])),
                "all_readings_count": len(smart.get("all_readings", [])),
            }
        super()._handle_coordinator_update()


class SevernTrentLatestDailySensor(SevernTrentBaseSensor):
    """Date of the latest available completed-day reading."""
    _attr_device_class = SensorDeviceClass.DATE
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, account_number):
        super().__init__(coordinator, account_number)
        self._attr_name = "Latest daily reading"
        self._attr_unique_id = f"{account_number}_latest_daily_reading"

    def _handle_coordinator_update(self):
        value = ((self.coordinator.data or {}).get("smart_meter") or {}).get("latest_daily_date")
        self._attr_native_value = datetime.fromisoformat(value).date() if value else None
        super()._handle_coordinator_update()


class SevernTrentHistorySensor(SevernTrentBaseSensor):
    """Expose import progress and the Energy Dashboard statistic identifier."""
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, account_number):
        super().__init__(coordinator, account_number)
        self._attr_name = "Water history status"
        self._attr_unique_id = f"{account_number}_history_status"

    def _handle_coordinator_update(self):
        history = (self.coordinator.data or {}).get("history") or {}
        self._attr_native_value = history.get("status", "no_daily_data")
        self._attr_extra_state_attributes = history
        super()._handle_coordinator_update()


class SevernTrentUsagePatternSensor(SevernTrentBaseSensor):
    """Optional sustained usage comparison, based only on complete recent data."""
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:water-alert"

    def __init__(self, coordinator, account_number):
        super().__init__(coordinator, account_number)
        self._attr_name = "Usage pattern"
        self._attr_unique_id = f"{account_number}_usage_pattern"

    def _handle_coordinator_update(self):
        pattern = (self.coordinator.data or {}).get("usage_pattern") or {}
        self._attr_native_value = pattern.get("status", "insufficient_data")
        self._attr_extra_state_attributes = pattern
        super()._handle_coordinator_update()
