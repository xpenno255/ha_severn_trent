"""Data update coordinator for Severn Trent Water integration."""
from __future__ import annotations

import logging
import re
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
        
        _LOGGER.info("=== Coordinator Update Starting ===")
        _LOGGER.info("Current time: %s (hour: %d)", now, now.hour)
        
        # Check if it's 6am or if we have missing data
        is_scheduled_time = now.hour == 6
        has_missing_data = len(self.missing_dates) > 0
        
        _LOGGER.info("Is scheduled time (6am): %s", is_scheduled_time)
        _LOGGER.info("Has missing data: %s (missing dates: %s)", has_missing_data, self.missing_dates)
        
        # If it's not 6am and we don't have missing data, just return existing data
        if not is_scheduled_time and not has_missing_data:
            _LOGGER.info("Not scheduled update time and no missing data, skipping update")
            _LOGGER.info("Returning existing data: %s", "empty" if not self.data else f"{len(self.data)} keys")
            return self.data or {}
        
        _LOGGER.info("Proceeding with data fetch...")
        
        try:
            # Authenticate first
            _LOGGER.info("Authenticating...")
            if not await self.hass.async_add_executor_job(self.api.authenticate):
                _LOGGER.error("Authentication failed during update")
                self.fetch_status = "failed"
                raise UpdateFailed("Authentication failed")
            
            _LOGGER.info("Authentication successful")
            
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
            
            _LOGGER.info("Fetching hourly data from %s to %s", start_dt, end_dt)
            hourly_data = await self.hass.async_add_executor_job(
                self.api.fetch_hourly_data, start_dt, end_dt
            )
            _LOGGER.info("Received %d hourly readings", len(hourly_data) if hourly_data else 0)
            
            # Fetch last 14 days of daily data (for week calculations)
            daily_start = datetime.combine(fetch_date - timedelta(days=13), dt_time.min)
            daily_end = datetime.combine(fetch_date + timedelta(days=1), dt_time.min)
            
            _LOGGER.info("Fetching daily data from %s to %s", daily_start, daily_end)
            daily_data = await self.hass.async_add_executor_job(
                self.api.fetch_daily_data, daily_start, daily_end
            )
            _LOGGER.info("Received %d daily readings", len(daily_data) if daily_data else 0)
            
            # Fetch monthly data (includes current month partial)
            _LOGGER.info("Fetching monthly data")
            monthly_data = await self.hass.async_add_executor_job(
                self.api.fetch_monthly_data
            )
            _LOGGER.info("Received %d monthly readings", len(monthly_data) if monthly_data else 0)
            
            # Fetch manual meter readings
            _LOGGER.info("Fetching manual meter readings")
            manual_data = await self.hass.async_add_executor_job(
                self.api.get_manual_meter_readings
            )
            _LOGGER.info("Manual meter data: %s", "received" if manual_data else "empty")
            
            # Inject hourly statistics
            if hourly_data:
                _LOGGER.info("Injecting hourly statistics...")
                await self._inject_hourly_statistics(hourly_data)
            
            # Inject daily statistics
            if daily_data:
                _LOGGER.info("Injecting daily statistics...")
                await self._inject_daily_statistics(daily_data)
            
            # Calculate and inject weekly statistics
            if daily_data:
                _LOGGER.info("Injecting weekly statistics...")
                await self._inject_weekly_statistics(daily_data)
            
            # Inject monthly statistics
            if monthly_data:
                _LOGGER.info("Injecting monthly statistics...")
                await self._inject_monthly_statistics(monthly_data)
            
            # Update success tracking
            self.last_successful_update = fetch_date.isoformat()
            self.fetch_status = "success"
            
            # Remove this date from missing dates if it was there
            if has_missing_data and fetch_date_str in self.missing_dates:
                self.missing_dates.remove(fetch_date_str)
            
            # Calculate current values for sensors
            _LOGGER.info("Calculating sensor values...")
            result = await self._calculate_sensor_values(daily_data, monthly_data, manual_data)
            
            _LOGGER.info("Successfully updated data for %s", fetch_date)
            _LOGGER.info("Result keys: %s", list(result.keys()) if result else "none")
            _LOGGER.info("=== Coordinator Update Complete ===")
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
        # Sanitize account number for statistic_id (only lowercase alphanumeric and underscores)
        safe_account = re.sub(r'[^a-z0-9_]', '_', self.account_number.lower())
        statistic_id = f"severn_trent:{safe_account}_hourly_usage"
        
        _LOGGER.info("Creating hourly statistics with ID: %s (account: %s)", statistic_id, self.account_number)
        
        metadata = StatisticMetaData(
            has_mean=False,
            has_sum=True,
            name=f"Severn Trent Hourly Usage ({self.account_number})",
            source="severn_trent",
            statistic_id=statistic_id,
            unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        )
        
        statistics = []
        cumulative_sum = 0
        
        for reading in hourly_data:
            try:
                start_dt = datetime.fromisoformat(reading["start_at"].replace("Z", "+00:00"))
                value = reading["value"]
                
                cumulative_sum += value
                
                # For external statistics: sum = cumulative total
                statistics.append(
                    StatisticData(
                        start=start_dt,
                        sum=cumulative_sum,  # CUMULATIVE total
                        state=value,         # This hour's usage
                    )
                )
            except (ValueError, KeyError) as e:
                _LOGGER.warning("Could not process hourly statistic: %s", e)
                continue
        
        if statistics:
            _LOGGER.info("Attempting to inject %d hourly statistics", len(statistics))
            await get_instance(self.hass).async_add_executor_job(
                async_add_external_statistics, self.hass, metadata, statistics
            )
            _LOGGER.info("Successfully injected %d hourly statistics", len(statistics))
    
    async def _inject_daily_statistics(self, daily_data: list[dict]) -> None:
        """Inject daily usage data into Home Assistant statistics."""
        safe_account = re.sub(r'[^a-z0-9_]', '_', self.account_number.lower())
        statistic_id = f"severn_trent:{safe_account}_daily_usage"
        
        _LOGGER.debug("📊 STATS: Preparing to inject %d daily statistics", len(daily_data))
        
        metadata = StatisticMetaData(
            has_mean=False,
            has_sum=True,  # Energy Dashboard requires sum for water
            name=f"Severn Trent Daily Usage ({self.account_number})",
            source="severn_trent",
            statistic_id=statistic_id,
            unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        )
        
        statistics = []
        cumulative_sum = 0  # Running total
        
        for reading in daily_data:
            try:
                # Use the date at midnight
                date_dt = datetime.fromisoformat(reading["date"] + "T00:00:00+00:00")
                value = reading["value"]
                
                # Calculate cumulative sum (total usage up to this point)
                cumulative_sum += value
                
                statistics.append(
                    StatisticData(
                        start=date_dt,
                        sum=cumulative_sum,  # CUMULATIVE total
                        state=value,          # Individual day's usage
                    )
                )
                
                # Log ALL values being injected
                _LOGGER.debug("📊 STATS: Injecting daily - Date: %s, Value: %.3f m³, Cumulative: %.3f m³", 
                              reading["date"], value, cumulative_sum)
                    
            except (ValueError, KeyError) as e:
                _LOGGER.warning("Could not process daily statistic: %s", e)
                continue
        
        if statistics:
            _LOGGER.debug("📊 STATS: Injecting %d daily statistics to ID: %s", len(statistics), statistic_id)
            await get_instance(self.hass).async_add_executor_job(
                async_add_external_statistics, self.hass, metadata, statistics
            )
            _LOGGER.info("Injected %d daily statistics", len(statistics))
    
    async def _inject_weekly_statistics(self, daily_data: list[dict]) -> None:
        """Calculate and inject weekly usage statistics (Monday-Sunday)."""
        safe_account = re.sub(r'[^a-z0-9_]', '_', self.account_number.lower())
        statistic_id = f"severn_trent:{safe_account}_weekly_usage"
        
        metadata = StatisticMetaData(
            has_mean=False,
            has_sum=True,
            name=f"Severn Trent Weekly Usage ({self.account_number})",
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
        cumulative_sum = 0
        
        for week_key, week_data in weekly_totals.items():
            # Store on Sunday's date with UTC timezone
            week_end_dt = datetime.combine(week_data["end"], dt_time.min)
            # Add UTC timezone info
            from datetime import timezone
            week_end_dt = week_end_dt.replace(tzinfo=timezone.utc)
            
            cumulative_sum += week_data["total"]
            
            statistics.append(
                StatisticData(
                    start=week_end_dt,
                    sum=cumulative_sum,  # CUMULATIVE total
                    state=round(week_data["total"], 3),  # This week's usage
                )
            )
        
        if statistics:
            await get_instance(self.hass).async_add_executor_job(
                async_add_external_statistics, self.hass, metadata, statistics
            )
            _LOGGER.info("Injected %d weekly statistics", len(statistics))
    
    async def _inject_monthly_statistics(self, monthly_data: list[dict]) -> None:
        """Inject monthly usage data into Home Assistant statistics."""
        safe_account = re.sub(r'[^a-z0-9_]', '_', self.account_number.lower())
        statistic_id = f"severn_trent:{safe_account}_monthly_usage"
        
        metadata = StatisticMetaData(
            has_mean=False,
            has_sum=True,
            name=f"Severn Trent Monthly Usage ({self.account_number})",
            source="severn_trent",
            statistic_id=statistic_id,
            unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        )
        
        statistics = []
        cumulative_sum = 0
        
        for reading in monthly_data:
            try:
                # Use the end date of the month (or current date for partial month)
                end_date_str = reading.get("end_date") or reading["start_date"]
                end_dt = datetime.fromisoformat(end_date_str + "T00:00:00+00:00")
                
                cumulative_sum += reading["value"]
                
                statistics.append(
                    StatisticData(
                        start=end_dt,
                        sum=cumulative_sum,      # CUMULATIVE total
                        state=reading["value"],  # This month's usage
                    )
                )
            except (ValueError, KeyError) as e:
                _LOGGER.warning("Could not process monthly statistic: %s", e)
                continue
        
        if statistics:
            await get_instance(self.hass).async_add_executor_job(
                async_add_external_statistics, self.hass, metadata, statistics
            )
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
        
        _LOGGER.debug("📊 SENSORS: Calculating sensor values for date: %s", yesterday)
        _LOGGER.debug("📊 SENSORS: Received %d daily readings", len(daily_data) if daily_data else 0)
        
        # Log the dates we have data for
        if daily_data:
            dates = [d["date"] for d in daily_data]
            _LOGGER.debug("📊 SENSORS: Daily data dates: %s ... %s (%d days)", 
                          dates[0] if dates else "none", 
                          dates[-1] if dates else "none", 
                          len(dates))
        
        # Previous day usage
        previous_day_usage = 0
        if daily_data:
            for reading in daily_data:
                if reading["date"] == yesterday.isoformat():
                    previous_day_usage = reading["value"]
                    _LOGGER.debug("📊 SENSORS: Found yesterday (%s): %.3f m³", yesterday, previous_day_usage)
                    break
        
        if previous_day_usage == 0:
            _LOGGER.warning("📊 SENSORS: WARNING - No data found for yesterday (%s)", yesterday)
        
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
        
        # Overnight usage (2am-5am from yesterday's hourly data)
        overnight_usage = await self._calculate_overnight_usage(yesterday)
        
        # Estimated meter reading
        estimated_reading = None
        usage_since_official = None
        days_since_official = None
        
        if manual_data and manual_data.get("latest_reading"):
            estimated_reading, usage_since_official, days_since_official = await self._calculate_estimated_meter_reading(
                manual_data, daily_data
            )
        
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
            "estimated_meter_reading": estimated_reading,
            "usage_since_official": usage_since_official,
            "days_since_official": days_since_official,
            "manual_meter": manual_data,
        }
    
    async def _calculate_overnight_usage(self, date: datetime.date) -> float | None:
        """Calculate overnight usage (2am-5am) for a specific date from statistics."""
        from homeassistant.components.recorder.statistics import (
            statistics_during_period,
        )
        
        safe_account = re.sub(r'[^a-z0-9_]', '_', self.account_number.lower())
        statistic_id = f"severn_trent:{safe_account}_hourly_usage"
        
        start_time = datetime.combine(date, dt_time(hour=2))
        end_time = datetime.combine(date, dt_time(hour=6))
        
        try:
            # Use executor via get_instance for database operations
            stats = await get_instance(self.hass).async_add_executor_job(
                statistics_during_period,
                self.hass,
                start_time,
                end_time,
                {statistic_id},
                "hour",
                None,
                {"sum"}
            )
            
            if statistic_id in stats and stats[statistic_id]:
                # Sum the STATE values (individual hourly usage), not cumulative sums
                total = sum(stat["state"] for stat in stats[statistic_id] if stat.get("state") is not None)
                return round(total, 3)
        except Exception as e:
            _LOGGER.warning("Could not calculate overnight usage: %s", e)
        
        return None
    
    async def _calculate_estimated_meter_reading(
        self, 
        manual_data: dict,
        daily_data: list[dict]
    ) -> tuple[float | None, float | None, int | None]:
        """Calculate estimated meter reading from official reading + daily usage."""
        latest_official = manual_data.get("latest_reading")
        official_date_str = manual_data.get("reading_date")
        
        if not latest_official or not official_date_str:
            return None, None, None
        
        try:
            # Parse official reading date
            official_date_str_clean = official_date_str.split("T")[0] if "T" in official_date_str else official_date_str
            official_date = datetime.fromisoformat(official_date_str_clean).date()
            
            # Calculate usage since official reading from daily data
            usage_since_official = 0
            for reading in daily_data:
                reading_date = datetime.fromisoformat(reading["date"]).date()
                if reading_date > official_date:
                    usage_since_official += reading["value"]
            
            # Calculate days since official reading
            today = datetime.now().date()
            days_since_official = (today - official_date).days
            
            estimated_reading = latest_official + usage_since_official
            
            return (
                round(estimated_reading, 3),
                round(usage_since_official, 3),
                days_since_official
            )
            
        except Exception as e:
            _LOGGER.error("Error calculating estimated meter reading: %s", e)
            return latest_official, None, None
    
    async def backfill_historical_data(self) -> None:
        """Backfill historical data from the API."""
        # This should ALWAYS appear in logs
        _LOGGER.warning("⚠️ SEVERN TRENT BACKFILL STARTING - If you see this, logging is working!")
        _LOGGER.info("Starting historical data backfill")
        
        try:
            # Authenticate
            _LOGGER.debug("⚠️ Step 1: Authenticating with API")
            if not await self.hass.async_add_executor_job(self.api.authenticate):
                _LOGGER.error("Authentication failed during backfill")
                return
            
            _LOGGER.debug("⚠️ Step 2: Authentication successful")
            
            now = datetime.now()
            
            # Fetch last 60 days of hourly data (matching daily data range)
            hourly_start = datetime.combine((now - timedelta(days=60)).date(), dt_time.min)
            hourly_end = datetime.combine(now.date(), dt_time.min)
            
            _LOGGER.debug("⚠️ Step 3: Fetching hourly data from %s to %s", hourly_start, hourly_end)
            hourly_data = await self.hass.async_add_executor_job(
                self.api.fetch_hourly_data, hourly_start, hourly_end
            )
            
            _LOGGER.debug("⚠️ Step 4: Received %d hourly data points", len(hourly_data) if hourly_data else 0)
            _LOGGER.debug("⚠️ Step 4a: Type of hourly_data: %s", type(hourly_data))
            
            if hourly_data:
                _LOGGER.debug("⚠️ Step 4b: Sample item: %s", str(hourly_data[0])[:200] if len(hourly_data) > 0 else "empty")
                _LOGGER.debug("⚠️ Step 5: About to inject hourly statistics...")
                try:
                    await self._inject_hourly_statistics(hourly_data)
                    _LOGGER.debug("⚠️ Step 6: Hourly statistics injection complete")
                except Exception as e:
                    _LOGGER.error("⚠️ ERROR in Step 5/6: %s", e, exc_info=True)
            else:
                _LOGGER.warning("No hourly data received from API")
            
            # Fetch last 60 days of daily data
            daily_start = datetime.combine((now - timedelta(days=60)).date(), dt_time.min)
            daily_end = datetime.combine(now.date(), dt_time.min)
            
            _LOGGER.debug("⚠️ Step 7: Fetching daily data from %s to %s", daily_start, daily_end)
            daily_data = await self.hass.async_add_executor_job(
                self.api.fetch_daily_data, daily_start, daily_end
            )
            
            _LOGGER.debug("⚠️ Step 8: Received %d daily data points", len(daily_data) if daily_data else 0)
            
            if daily_data:
                _LOGGER.debug("⚠️ Step 9: Injecting daily statistics")
                try:
                    await self._inject_daily_statistics(daily_data)
                    _LOGGER.debug("⚠️ Step 10: Daily statistics injection complete")
                except Exception as e:
                    _LOGGER.error("⚠️ ERROR in Step 9/10: %s", e, exc_info=True)
                
                _LOGGER.debug("⚠️ Step 11: Injecting weekly statistics")
                try:
                    await self._inject_weekly_statistics(daily_data)
                    _LOGGER.debug("⚠️ Step 12: Weekly statistics injection complete")
                except Exception as e:
                    _LOGGER.error("⚠️ ERROR in Step 11/12: %s", e, exc_info=True)
            else:
                _LOGGER.warning("No daily data received from API")
            
            # Fetch all available monthly data
            _LOGGER.debug("⚠️ Step 13: Fetching monthly data")
            monthly_data = await self.hass.async_add_executor_job(
                self.api.fetch_monthly_data
            )
            
            _LOGGER.debug("⚠️ Step 14: Received %d monthly data points", len(monthly_data) if monthly_data else 0)
            
            if monthly_data:
                _LOGGER.debug("⚠️ Step 15: Injecting monthly statistics")
                try:
                    await self._inject_monthly_statistics(monthly_data)
                    _LOGGER.debug("⚠️ Step 16: Monthly statistics injection complete")
                except Exception as e:
                    _LOGGER.error("⚠️ ERROR in Step 15/16: %s", e, exc_info=True)
            else:
                _LOGGER.warning("No monthly data received from API")
            
            # Fetch manual meter readings for sensor calculations
            _LOGGER.debug("⚠️ Step 17: Fetching manual meter readings")
            manual_data = await self.hass.async_add_executor_job(
                self.api.get_manual_meter_readings
            )
            _LOGGER.debug("⚠️ Step 18: Manual meter data received: %s", "yes" if manual_data else "no")
            
            # Calculate sensor values using the fetched data
            _LOGGER.debug("⚠️ Step 19: Calculating sensor values to update coordinator data")
            if daily_data:
                try:
                    sensor_data = await self._calculate_sensor_values(daily_data, monthly_data, manual_data)
                    _LOGGER.debug("⚠️ Step 20: Sensor values calculated, updating coordinator data")
                    _LOGGER.debug("⚠️ Step 20a: Sensor data keys: %s", list(sensor_data.keys()) if sensor_data else "none")
                    
                    # Update the coordinator's data
                    self.data = sensor_data
                    
                    # Trigger a coordinator update to refresh all sensors
                    _LOGGER.debug("⚠️ Step 21: Triggering coordinator update to refresh sensors")
                    self.async_set_updated_data(sensor_data)
                    _LOGGER.debug("⚠️ Step 22: Sensors updated with new data")
                    
                except Exception as e:
                    _LOGGER.error("⚠️ ERROR calculating/updating sensor values: %s", e, exc_info=True)
            
            _LOGGER.debug("⚠️ Step 23: Historical data backfill completed successfully")
            _LOGGER.warning("⚠️ BACKFILL COMPLETE - Statistics injected AND sensors updated!")
            
        except Exception as e:
            _LOGGER.error("Error during historical data backfill: %s", e, exc_info=True)
