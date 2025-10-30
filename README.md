# Severn Trent Water Integration - Version 2.0

## Complete Redesign with Statistics and Enhanced Features

This is a major update to the Severn Trent Water Home Assistant integration with a completely redesigned architecture focused on proper data storage, accurate statistics, and enhanced leak detection.

---

## What's New in Version 2.0

### ✨ Key Features

1. **Direct Statistics Injection**
   - Hourly usage data injected directly into Home Assistant's statistics database
   - Daily usage totals stored as statistics
   - Weekly totals (Monday-Sunday) stored as statistics
   - Monthly totals stored as statistics
   - All data appears natively in HA's history graphs and energy dashboard

2. **Scheduled Updates at 6am Daily**
   - Fetches complete previous day's data when it's fully available
   - Avoids partial/incomplete readings during the day
   - Retry logic with hourly attempts if updates fail

3. **Historical Data Backfill**
   - Optional backfill on initial setup
   - Manual backfill service available
   - Imports last 7 days of hourly data, 60 days of daily data, and all available monthly data

4. **New Sensors**
   - **Previous Day Usage** - Total water usage for yesterday
   - **Week to Date** - Cumulative usage for current week (Monday-Sunday, resets weekly)
   - **Month to Date** - Cumulative usage for current month
   - **Overnight Usage** - Usage between 2am-5am (leak detection indicator)
   - **Overnight Leak Alert** - Binary sensor that alerts if >0.01m³ used overnight
   - **Meter Reading** - Official meter reading from Severn Trent
   - **Estimated Meter Reading** - Current estimated reading based on official reading + daily usage

5. **Fixed State Classes**
   - Corrected state class usage to prevent incorrect statistics accumulation
   - Previous day and weekly sensors now use MEASUREMENT instead of TOTAL

---

## Architecture Overview

### Data Flow

```
6am Daily Update:
1. API Fetch → Hourly data for yesterday
2. API Fetch → Daily data for last 14 days  
3. API Fetch → Monthly data (full year including partial current month)
4. API Fetch → Manual meter readings

↓

5. Inject to Statistics Database:
   - Hourly statistics (each hour as separate entry)
   - Daily statistics (one per day)
   - Weekly statistics (Monday-Sunday totals, stored on Sunday)
   - Monthly statistics (stored on last day of month)

↓

6. Calculate Sensor Values:
   - Previous Day Usage (from daily data)
   - Week to Date (sum Monday-Sunday for current week)
   - Month to Date (from monthly API data)
   - Overnight Usage (2am-5am from statistics)
   - Overnight Leak Alert (overnight > 0.01m³)
```

### Files Modified

1. **`api.py`** - New methods for fetching hourly, daily, and monthly data
2. **`coordinator.py`** (NEW) - Handles scheduled updates and statistics injection
3. **`sensor.py`** - Completely rewritten with new sensor classes
4. **`config_flow.py`** - Added backfill checkbox
5. **`__init__.py`** - Updated to use new coordinator and register services
6. **`services.yaml`** (NEW) - Defines backfill service
7. **`strings.json`** - Added backfill step text

---

## Sensors Explained

### Previous Day Usage
- **Updates**: 6am daily
- **Value**: Total water usage for the previous complete day
- **State Class**: MEASUREMENT
- **Use Case**: See exactly how much water was used yesterday

### Week to Date
- **Updates**: 6am daily
- **Value**: Cumulative usage from Monday to yesterday
- **Resets**: Every Monday
- **State Class**: MEASUREMENT
- **Use Case**: Track weekly usage patterns, resets each week for easy comparison

### Month to Date
- **Updates**: 6am daily
- **Value**: Cumulative usage for the current month (from API monthly data)
- **Resets**: First day of each month
- **State Class**: MEASUREMENT
- **Use Case**: Monitor monthly consumption against budget/targets

### Overnight Usage
- **Updates**: 6am daily
- **Value**: Total water usage between 2am-5am (previous night)
- **Calculation**: Queries hourly statistics for 2am-5am window
- **State Class**: MEASUREMENT
- **Use Case**: Identify baseline consumption and potential leaks

### Overnight Leak Alert
- **Type**: Binary Sensor
- **Updates**: 6am daily
- **Threshold**: 0.01 m³ (10 liters)
- **State**: ON if overnight usage > threshold, OFF otherwise
- **Use Case**: Automatic alerts for potential water leaks during low-usage hours

### Meter Reading
- **Updates**: When Severn Trent records a new reading
- **Value**: Official cumulative meter reading
- **State Class**: TOTAL_INCREASING
- **Use Case**: Track official readings from Severn Trent

### Estimated Meter Reading
- **Updates**: 6am daily
- **Calculation**: Last official reading + sum of daily usage since that reading
- **State Class**: TOTAL_INCREASING
- **Use Case**: Estimate current meter position between official readings

---

## Statistics Entities

These are not visible as sensors but are queryable in history/energy dashboard:

### `severn_trent:{account}:hourly_usage`
- One entry per hour
- Shows water usage for each hour of each day
- Perfect for detailed usage analysis

### `severn_trent:{account}:daily_usage`
- One entry per day
- Total usage for each complete day

### `severn_trent:{account}:weekly_usage`
- One entry per week (stored on Sunday)
- Total usage for each Monday-Sunday period

### `severn_trent:{account}:monthly_usage`
- One entry per month
- Total usage for each calendar month

---

## Installation & Setup

### First Time Setup

1. Install the integration through HACS or manually
2. Go to Settings → Devices & Services → Add Integration
3. Search for "Severn Trent Water"
4. Enter your email and password
5. Select your account (if you have multiple)
6. **Choose backfill option** (recommended: YES)
   - This will import historical data:
     - Last 7 days of hourly data
     - Last 60 days of daily data
     - All available monthly data (from June 2025)
7. Wait for setup to complete (backfill may take 1-2 minutes)

### Manual Backfill

If you didn't backfill during setup or want to refresh historical data:

**Option 1: Service Call in Developer Tools**
```yaml
service: severn_trent.backfill_history
data:
  account_number: "YOUR_ACCOUNT_NUMBER"  # Optional, omit to backfill all accounts
```

**Option 2: Automation**
```yaml
automation:
  - alias: "Backfill Severn Trent Data"
    trigger:
      - platform: time
        at: "03:00:00"
    action:
      - service: severn_trent.backfill_history
```

---

## Update Schedule

### Daily at 6am
- Fetches previous day's complete data
- Injects statistics
- Updates all sensors
- **Why 6am?** API data is most reliable for complete previous days

### Retry Logic
- If 6am update fails → retry every hour until successful
- Tracks missing dates
- Automatically fetches missed data on next successful connection

---

## Data Quality & Reliability

### API Data Sources

The integration uses different API endpoints optimally:

1. **Hourly Data** - `HOUR_INTERVAL` frequency
   - Most granular data
   - Used for overnight leak detection
   - Fetched for previous day only

2. **Daily Data** - Aggregated from hourly
   - Used for week-to-date calculations
   - Fetched for last 14 days (ensures we have full weeks)

3. **Monthly Data** - `MONTH_INTERVAL` frequency  
   - Includes partial current month
   - Used for month-to-date sensor
   - Most efficient for long-term data

### State Class Fixes

Previous version incorrectly used `TOTAL` state class for sensors that should have been `MEASUREMENT`. This caused Home Assistant to calculate deltas incorrectly, resulting in stepped graphs.

**Fixed Sensors:**
- Yesterday Usage → Previous Day Usage (now MEASUREMENT)
- Weekly Total → Week to Date (now MEASUREMENT)

**Explanation:**
- `TOTAL` = cumulative value that only increases (like a meter reading)
- `MEASUREMENT` = point-in-time value (like daily usage)
- Using correct state classes ensures proper statistics and graphs

---

## Estimated Meter Reading Calculation

### Old Method (❌ Incorrect)
```python
official_reading + sum(monthly_readings >= official_date)
```
**Problem:** Used monthly data which could include partial months and double-count usage

### New Method (✅ Correct)
```python
official_reading + sum(daily_statistics > official_date)
```
**Improvement:** Uses daily statistics for accurate day-by-day tracking

**Example:**
- Official reading: 1000.00 m³ on October 1st
- Daily usage Oct 2-27: 7.5 m³
- Estimated reading: 1000.00 + 7.5 = 1007.5 m³

---

## Troubleshooting

### Sensors showing "Unknown" or "Unavailable"

**Cause:** Waiting for 6am update or statistics not yet populated

**Solution:**
1. Wait until after 6am for first update
2. Run manual backfill: `severn_trent.backfill_history`
3. Check logs for errors

### No historical data in graphs

**Cause:** Backfill wasn't run or statistics injection failed

**Solution:**
1. Call backfill service manually
2. Check Home Assistant logs for errors
3. Verify recorder is enabled

### Overnight leak sensor always OFF

**Cause:** No hourly statistics for 2am-5am period yet

**Solution:**
1. Wait 24 hours after setup for first overnight period
2. Verify hourly statistics exist: Developer Tools → Statistics

### Week to Date not resetting on Monday

**Cause:** Update hasn't run yet on Monday

**Solution:**
- Sensor updates at 6am, so will reset Monday at 6am
- Check coordinator logs at 6am

---

## API Rate Limits & Efficiency

### Update Strategy
- **Single daily update at 6am**
- Minimal API calls (3 queries: hourly, daily, monthly)
- Backfill is one-time or manual only

### API Queries Per Day
- Normal operation: 3 queries at 6am
- With retries (if failure): Up to 3 queries per hour until success
- Backfill (manual): ~3 queries once

---

## Energy Dashboard Integration

All statistics can be used in Home Assistant's Energy Dashboard:

1. Go to Settings → Dashboards → Energy
2. Add Water source
3. Select statistic: `severn_trent:{account}:hourly_usage`
4. Configure costs if desired

You can also create custom energy cards using:
- `severn_trent:{account}:daily_usage` for less detailed view
- `severn_trent:{account}:weekly_usage` for weekly trends
- `severn_trent:{account}:monthly_usage` for monthly comparison

---

## Example Automations

### Leak Alert Notification
```yaml
automation:
  - alias: "Water Leak Detected"
    trigger:
      - platform: state
        entity_id: binary_sensor.severn_trent_overnight_leak_alert
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          title: "Potential Water Leak!"
          message: >
            {{ states('sensor.severn_trent_overnight_usage') }}m³ used overnight.
            This is above the normal threshold.
```

### Weekly Usage Report
```yaml
automation:
  - alias: "Weekly Water Usage Report"
    trigger:
      - platform: time
        at: "09:00:00"
    condition:
      - condition: time
        weekday:
          - mon
    action:
      - service: notify.mobile_app
        data:
          title: "Last Week's Water Usage"
          message: >
            You used {{ states('sensor.severn_trent_week_to_date') }}m³ last week.
```

### High Usage Alert
```yaml
automation:
  - alias: "High Daily Usage Alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.severn_trent_previous_day_usage
        above: 0.5  # 500 liters
    action:
      - service: notify.mobile_app
        data:
          title: "High Water Usage Yesterday"
          message: >
            Yesterday's usage was {{ states('sensor.severn_trent_previous_day_usage') }}m³.
            This is higher than normal.
```

---

## Migration from Version 1.x

### What happens to old data?

Old sensors will be removed. Historical data from statistics will remain.

### Steps to migrate:

1. **Backup your Home Assistant** (recommended)
2. Remove old integration
3. Install new version
4. Re-add integration with same credentials
5. **Enable backfill** to import historical data
6. Update any automations/dashboards to use new sensor names

### Sensor Name Changes

| Old Sensor | New Sensor |
|------------|------------|
| `sensor.severn_trent_yesterday_usage` | `sensor.severn_trent_previous_day_usage` |
| `sensor.severn_trent_weekly_total` | `sensor.severn_trent_week_to_date` |
| `sensor.severn_trent_daily_average` | (removed - calculate from statistics) |
| `sensor.severn_trent_meter_reading` | `sensor.severn_trent_meter_reading` (unchanged) |
| `sensor.severn_trent_estimated_meter_reading` | `sensor.severn_trent_estimated_meter_reading` (unchanged, but fixed calculation) |

---

## Technical Details

### Statistics Format

#### Hourly Statistics
```python
StatisticData(
    start=datetime(2025, 10, 27, 8, 0, 0),  # 8am
    state=0.106,  # 106 liters used this hour
    sum=0.106
)
```

#### Daily Statistics
```python
StatisticData(
    start=datetime(2025, 10, 27, 0, 0, 0),  # Midnight
    state=0.395,  # 395 liters used this day
    sum=0.395
)
```

#### Weekly Statistics
```python
StatisticData(
    start=datetime(2025, 10, 27, 0, 0, 0),  # Sunday (end of week)
    state=2.156,  # Total for Mon-Sun week
    sum=2.156
)
```

### Coordinator Update Logic

```python
async def _async_update_data():
    now = datetime.now()
    
    # Only update at 6am or if we have missing data
    if now.hour != 6 and not self.missing_dates:
        return self.data  # Skip update
    
    # Fetch yesterday's data
    fetch_date = yesterday if not self.missing_dates else self.missing_dates[0]
    
    # Fetch all data types
    hourly = fetch_hourly_data(fetch_date)
    daily = fetch_daily_data(last_14_days)
    monthly = fetch_monthly_data()
    manual = fetch_manual_readings()
    
    # Inject to statistics
    inject_hourly_statistics(hourly)
    inject_daily_statistics(daily)
    inject_weekly_statistics(daily)  # Calculate weeks from daily
    inject_monthly_statistics(monthly)
    
    # Calculate sensor values
    return calculate_current_values(...)
```

---

## Support & Feedback

### Logs

Enable debug logging for detailed information:

```yaml
logger:
  default: info
  logs:
    custom_components.severn_trent: debug
```

### Common Log Messages

✅ **Success:**
```
Successfully updated data for 2025-10-27
Injected 24 hourly statistics
Injected 1 daily statistics
```

⚠️ **Retry:**
```
Authentication failed during update
Fetch status: failed
Adding 2025-10-27 to missing_dates
```

❌ **Error:**
```
Error fetching HOUR_INTERVAL data: HTTP 401
Could not calculate overnight usage: No statistics found
```

---

## Future Enhancements

Potential features for future versions:

1. **Cost Tracking** - Add water/wastewater rates for cost calculation
2. **Usage Predictions** - ML-based prediction of daily/weekly usage
3. **Comparison Features** - Compare to previous week/month/year
4. **Multiple Meters** - Support for properties with multiple meters
5. **Tariff Support** - Handle different pricing tiers
6. **Irrigation Mode** - Separate indoor vs outdoor water tracking

---

## Credits

- Original integration by @xpenno255
- Version 2.0 redesign with assistance from Claude (Anthropic)
- Severn Trent API documentation (unofficial)

---

## License

This integration is provided as-is with no warranty. Use at your own risk.
