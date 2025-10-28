"""Data update coordinator for Severn Trent Water integration."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, time as dt_time
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
    StatisticData,
    StatisticMetaData,
)
from homeassistant.const import UnitOfVolume

from .api import SevernTrentAPI

_LOGGER = logging.getLogger(__name__)

class SevernTrentDataCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Severn Trent data."""

    def __init__(self, hass: HomeAssistant, api: SevernTrentAPI, account_number: str):
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Severn Trent Water",
            update_interval=timedelta(hours=1),
        )
        self.api = api
        self.account_number = account_number
        self.last_successful_update: str | None = None
        self.missing_dates: list[str] = []
        self.fetch_status = "pending"
        
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        now = datetime.now()
        
        # Check if it's 6am or if we have missing data
        is_scheduled_time = now.hour == 6
        has_missing_data = len(self.missing_dates) > 0
        
        # If it's not 6am and we don't have missing data, just return existing data
        if not is_scheduled_time and not has_missing_data:
            _LOGGER.debug("Not scheduled update time (6am) and no missing data, skipping update")
            return self.data or {}
        
        try:
            # Authenticate first
            if not await self.hass.async_add_executor_job(self.api.authenticate):
                _LOGGER.error("Authentication failed during update")
                self.fetch_status = "failed"
                raise UpdateFailed("Authentication failed")
            
            # Determine what date to fetch
            yesterday = (now - timedelta(days=1)).date()
            
            # If we have missing dates, fetch the oldest one
            if has_missing_data:
                fetch_date_str = self.missing_dates[0]
                fetch_date = datetime.fromisoformat(fetch_date_str).date()
                _LOGGER.info("Fetching missing data for %s", fetch_date)
            else:
                fetch_date = yesterday
                _LOGGER.info("Fetching data for yesterday: %s", fetch_date)
            
            # Fetch yesterday's hourly data
            start_dt = datetime.combine(fetch_date, dt_time.min)
            end_dt = datetime.combine(fetch_date + timedelta(days=1), dt_time.min)
            
            hourly_data = await self.hass.async_add_executor_job(
                self.api.fetch_hourly_data, start_dt, end_dt
            )
            
            # Fetch last 14 days of daily data (for week calculations)
            daily_start = datetime.combine(fetch_date - timedelta(days=13), dt_time.min)
            daily_end = datetime.combine(fetch_date + timedelta(days=1), dt_time.min)
            
            daily_data = await self.hass.async_add_executor_job(
                self.api.fetch_daily_data, daily_start, daily_end
            )
            
            # Fetch monthly data (includes current month partial)
            monthly_data = await self.hass.async_add_executor_job(
                self.api.fetch_monthly_data
            )
            
            # Fetch manual meter readings
            manual_data = await self.hass.async_add_executor_job(
                self.api.get_manual_meter_readings
            )
            
            # Inject hourly statistics
            if hourly_data:
                await self._inject_hourly_statistics(hourly_data)
            
            # Inject daily statistics
            if daily_data:
                await self._inject_daily_statistics(daily_data)
            
            # Calculate and inject weekly statistics
            if daily_data:
                await self._inject_weekly_statistics(daily_data)
            
            # Inject monthly statistics
            if monthly_data:
                await self._inject_monthly_statistics(monthly_data)
            
            # Update success tracking
            self.last_successful_update = fetch_date.isoformat()
            self.fetch_status = "success"
            
            # Remove this date from missing dates if it was there
            if has_missing_data and fetch_date_str in self.missing_dates:
                self.missing_dates.remove(fetch_date_str)
            
            # Calculate current values for sensors
            result = await self._calculate_sensor_values(daily_data, monthly_data, manual_data)
            
            _LOGGER.info("Successfully updated data for %s", fetch_date)
            return result
            
        except Exception as err:
            _LOGGER.error("Error updating data: %s", err, exc_info=True)
            self.fetch_status = "failed"
            
            # Add to missing dates if not already there
            if fetch_date.isoformat() not in self.missing_dates:
                self.missing_dates.append(fetch_date.isoformat())
            
            raise UpdateFailed(f"Error communicating with API: {err}")
    
    async def _inject_hourly_statistics(self, hourly_data: list[dict]) -> None:
        """Inject hourly usage data into Home Assistant statistics."""
        statistic_id = f"severn_trent:{self.account_number}:hourly_usage"
        
        metadata = StatisticMetaData(
            has_mean=False,
            has_sum=True,
            name="Severn Trent Hourly Usage",
            source="severn_trent",
            statistic_id=statistic_id,
            unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        )
        
        statistics = []
        for reading in hourly_data:
            try:
                start_dt = datetime.fromisoformat(reading["start_at"].replace("Z", "+00:00"))
                
                statistics.append(
                    StatisticData(
                        start=start_dt,
                        state=reading["value"],
                        sum=reading["value"],
                    )
                )
            except (ValueError, KeyError) as e:
                _LOGGER.warning("Could not process hourly statistic: %s", e)
                continue
        
        if statistics:
            async_add_external_statistics(self.hass, metadata, statistics)
            _LOGGER.info("Injected %d hourly statistics", len(statistics))
    
    async def _inject_daily_statistics(self, daily_data: list[dict]) -> None:
        """Inject daily usage data into Home Assistant statistics."""
        statistic_id = f"severn_trent:{self.account_number}:daily_usage"
        
        metadata = StatisticMetaData(
            has_mean=False,
            has_sum=True,
            name="Severn Trent Daily Usage",
            source="severn_trent",
            statistic_id=statistic_id,
            unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        )
        
        statistics = []
        for reading in daily_data:
            try:
                # Use the date at midnight
                date_dt = datetime.fromisoformat(reading["date"] + "T00:00:00+00:00")
                
                statistics.append(
                    StatisticData(
                        start=date_dt,
                        state=reading["value"],
                        sum=reading["value"],
                    )
                )
            except (ValueError, KeyError) as e:
                _LOGGER.warning("Could not process daily statistic: %s", e)
                continue
        
        if statistics:
            async_add_external_statistics(self.hass, metadata, statistics)
            _LOGGER.info("Injected %d daily statistics", len(statistics))
    
    async def _inject_weekly_statistics(self, daily_data: list[dict]) -> None:
        """Calculate and inject weekly usage statistics (Monday-Sunday)."""
        statistic_id = f"severn_trent:{self.account_number}:weekly_usage"
        
        metadata = StatisticMetaData(
            has_mean=False,
            has_sum=True,
            name="Severn Trent Weekly Usage",
            source="severn_trent",
            statistic_id=statistic_id,
            unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        )
        
        # Group daily data by week (Monday-Sunday)
        weekly_totals = {}
        for reading in daily_data:
            try:
                date_obj = datetime.fromisoformat(reading["date"]).date()
                
                # Find the Monday of this week
                days_since_monday = date_obj.weekday()  # 0 = Monday, 6 = Sunday
                week_start = date_obj - timedelta(days=days_since_monday)
                week_end = week_start + timedelta(days=6)  # Sunday
                
                week_key = week_start.isoformat()
                
                if week_key not in weekly_totals:
                    weekly_totals[week_key] = {
                        "start": week_start,
                        "end": week_end,
                        "total": 0,
                        "days_included": set()
                    }
                
                weekly_totals[week_key]["total"] += reading["value"]
                weekly_totals[week_key]["days_included"].add(date_obj.isoformat())
                
            except (ValueError, KeyError) as e:
                _LOGGER.warning("Could not process weekly data: %s", e)
                continue
        
        # Create statistics only for complete weeks (Sunday reached)
        statistics = []
        for week_key, week_data in weekly_totals.items():
            # Only add if we have data through Sunday or week is complete
            week_end_dt = datetime.combine(week_data["end"], dt_time.min)
            
            # Store on Sunday's date
            statistics.append(
                StatisticData(
                    start=week_end_dt.replace(tzinfo=None),
                    state=round(week_data["total"], 3),
                    sum=round(week_data["total"], 3),
                )
            )
        
        if statistics:
            async_add_external_statistics(self.hass, metadata, statistics)
            _LOGGER.info("Injected %d weekly statistics", len(statistics))
    
    async def _inject_monthly_statistics(self, monthly_data: list[dict]) -> None:
        """Inject monthly usage data into Home Assistant statistics."""
        statistic_id = f"severn_trent:{self.account_number}:monthly_usage"
        
        metadata = StatisticMetaData(
            has_mean=False,
            has_sum=True,
            name="Severn Trent Monthly Usage",
            source="severn_trent",
            statistic_id=statistic_id,
            unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        )
        
        statistics = []
        for reading in monthly_data:
            try:
                # Use the end date of the month (or current date for partial month)
                end_date_str = reading.get("end_date") or reading["start_date"]
                end_dt = datetime.fromisoformat(end_date_str + "T00:00:00+00:00")
                
                statistics.append(
                    StatisticData(
                        start=end_dt,
                        state=reading["value"],
                        sum=reading["value"],
                    )
                )
            except (ValueError, KeyError) as e:
                _LOGGER.warning("Could not process monthly statistic: %s", e)
                continue
        
        if statistics:
            async_add_external_statistics(self.hass, metadata, statistics)
            _LOGGER.info("Injected %d monthly statistics", len(statistics))
    
    async def _calculate_sensor_values(
        self, 
        daily_data: list[dict], 
        monthly_data: list[dict],
        manual_data: dict
    ) -> dict[str, Any]:
        """Calculate current values for all sensors."""
        now = datetime.now()
        yesterday = (now - timedelta(days=1)).date()
        
        # Previous day usage
        previous_day_usage = 0
        if daily_data:
            for reading in daily_data:
                if reading["date"] == yesterday.isoformat():
                    previous_day_usage = reading["value"]
                    break
        
        # Week to date (current week Monday-Sunday)
        days_since_monday = now.weekday()
        week_start = (now - timedelta(days=days_since_monday)).date()
        
        week_to_date = 0
        week_days_included = 0
        if daily_data:
            for reading in daily_data:
                reading_date = datetime.fromisoformat(reading["date"]).date()
                if week_start <= reading_date <= yesterday:
                    week_to_date += reading["value"]
                    week_days_included += 1
        
        # Month to date (from monthly API data)
        month_to_date = 0
        current_month_str = now.strftime("%Y-%m")
        if monthly_data:
            for reading in monthly_data:
                if reading["start_date"].startswith(current_month_str):
                    month_to_date = reading["value"]
                    break
        
        # Overnight usage (2am-5am from yesterday) - will be calculated from hourly data
        # For now, we'll calculate it when we have the hourly data stored
        overnight_usage = None  # Will be populated by sensor from statistics
        
        return {
            "last_successful_update": self.last_successful_update,
            "fetch_status": self.fetch_status,
            "missing_dates": self.missing_dates,
            "previous_day": {
                "date": yesterday.isoformat(),
                "usage": round(previous_day_usage, 3),
            },
            "week_to_date": {
                "start_date": week_start.isoformat(),
                "usage": round(week_to_date, 3),
                "days_included": week_days_included,
            },
            "month_to_date": {
                "month": current_month_str,
                "usage": round(month_to_date, 3),
            },
            "overnight_usage": overnight_usage,
            "manual_meter": manual_data,
        }
    
    async def backfill_historical_data(self) -> None:
        """Backfill historical data from the API."""
        _LOGGER.info("Starting historical data backfill")
        
        try:
            # Authenticate
            if not await self.hass.async_add_executor_job(self.api.authenticate):
                _LOGGER.error("Authentication failed during backfill")
                return
            
            now = datetime.now()
            
            # Fetch last 7 days of hourly data
            hourly_start = datetime.combine((now - timedelta(days=7)).date(), dt_time.min)
            hourly_end = datetime.combine(now.date(), dt_time.min)
            
            _LOGGER.info("Backfilling hourly data from %s to %s", hourly_start, hourly_end)
            hourly_data = await self.hass.async_add_executor_job(
                self.api.fetch_hourly_data, hourly_start, hourly_end
            )
            
            if hourly_data:
                await self._inject_hourly_statistics(hourly_data)
                _LOGGER.info("Backfilled hourly data: %d records", len(hourly_data))
            
            # Fetch last 60 days of daily data
            daily_start = datetime.combine((now - timedelta(days=60)).date(), dt_time.min)
            daily_end = datetime.combine(now.date(), dt_time.min)
            
            _LOGGER.info("Backfilling daily data from %s to %s", daily_start, daily_end)
            daily_data = await self.hass.async_add_executor_job(
                self.api.fetch_daily_data, daily_start, daily_end
            )
            
            if daily_data:
                await self._inject_daily_statistics(daily_data)
                await self._inject_weekly_statistics(daily_data)
                _LOGGER.info("Backfilled daily data: %d records", len(daily_data))
            
            # Fetch all available monthly data
            _LOGGER.info("Backfilling monthly data")
            monthly_data = await self.hass.async_add_executor_job(
                self.api.fetch_monthly_data
            )
            
            if monthly_data:
                await self._inject_monthly_statistics(monthly_data)
                _LOGGER.info("Backfilled monthly data: %d records", len(monthly_data))
            
            _LOGGER.info("Historical data backfill completed successfully")
            
        except Exception as e:
            _LOGGER.error("Error during historical data backfill: %s", e, exc_info=True)
