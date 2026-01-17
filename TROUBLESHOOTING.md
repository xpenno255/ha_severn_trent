# Troubleshooting Data Discrepancies

This guide helps diagnose discrepancies between the integration values and the Severn Trent website.

## Common Causes of Discrepancies

### 1. **Time Zone Differences**
- The integration uses local time for "yesterday" and week calculations
- Severn Trent API may use UTC or a different time zone
- This can cause off-by-one-day errors

### 2. **Data Aggregation Methods**
- **Hourly to Daily**: We aggregate hourly readings into daily totals
- **Daily to Weekly**: We sum daily readings for week calculations
- **Monthly Data**: May include partial periods differently
- The website might use different aggregation logic

### 3. **Data Availability Timing**
- Smart meter data has processing delays
- "Yesterday" might not include the most recent hours
- Different systems may have different data freshness

### 4. **Reading Types**
- **HOUR_INTERVAL**: Hourly smart meter readings
- **DAY_INTERVAL**: Daily aggregated readings
- **MONTH_INTERVAL**: Monthly aggregated readings
- The website might prioritize different reading types

### 5. **Week Calculations**
- Integration uses Monday as week start
- Website might use Sunday or a different day
- This can cause weekly totals to differ

### 6. **Meter Reading vs Usage**
- **Cumulative readings**: Total meter position (like odometer)
- **Usage readings**: Water consumed in a period
- Make sure you're comparing like-with-like

## Enable Debug Logging

Add this to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.severn_trent: debug
```

Then restart Home Assistant.

## What to Check in Logs

Look for these key log messages:

### Daily Data Processing
```
Found X hourly measurements
Daily totals: {'2024-01-15': 1.234, '2024-01-16': 2.345}
Yesterday (2024-01-16): 2.345 m³
```

### Week Calculations
```
Current week starts: 2024-01-15
Previous week: 2024-01-08 to 2024-01-14
Week to date usage: 5.678 m³ (3 days)
Previous week usage: 12.345 m³
```

### Monthly Data
```
Found X monthly readings
Monthly reading: 2024-01-01 = 9.841 m³
```

### Estimated Meter Reading
```
Calculating estimated reading:
  Official reading: 272.0 on 2024-10-15
  Monthly readings available: 3
  Daily readings available: 16
  Daily reading: 2024-10-16 = 0.123 m³
  Monthly reading: 2024-11-01 = 9.2 m³ (included)
  Total usage since official: 11.5 m³
  Estimated current: 283.5 m³
```

## Comparison Checklist

When comparing with the Severn Trent website:

- [ ] **Check the dates**: Are you comparing the same time period?
- [ ] **Check the time zone**: Does the website show times in GMT/BST?
- [ ] **Check units**: Both should be in m³ (cubic meters)
- [ ] **Check reading type**: Usage vs cumulative reading
- [ ] **Check week definition**: Monday-Sunday vs Sunday-Saturday
- [ ] **Note the timestamp**: When was data last updated on each platform?

## Known Differences

### Yesterday's Usage
- **Integration**: Sums all hourly readings for the previous calendar day
- **Website**: May show a different aggregation period

### Week Totals
- **Integration**: Monday (00:00) to Sunday (23:59)
- **Website**: May use different week boundaries

### Estimated Meter Reading
- **Integration**: Official reading + daily (partial month) + monthly (complete months)
- **Website**: May use different estimation method

## Reporting Issues

If discrepancies persist, please report with:

1. **Screenshots**: Both integration and website values
2. **Dates**: Clearly show what period you're comparing
3. **Logs**: Debug logs showing the calculations (remove sensitive info)
4. **Time**: When you captured both values
5. **Time Zone**: Your Home Assistant time zone setting

## Manual Verification

You can manually verify calculations:

### For Yesterday's Usage:
1. Check logs for hourly measurements for that date
2. Sum all hourly values yourself
3. Compare with integration value

### For Weekly Usage:
1. Check logs for daily totals
2. Sum the days in the week period
3. Compare with integration value

### For Estimated Reading:
1. Note your last official reading and date from logs
2. Add up monthly usage since that date (from logs)
3. Add any daily usage for partial months
4. Compare with integration value

## Quick Fixes to Try

1. **Reload the integration**
   - Settings → Devices & Services → Severn Trent → Reload

2. **Force an update**
   ```yaml
   service: homeassistant.update_entity
   target:
     entity_id: sensor.severn_trent_yesterday_usage
   ```

3. **Check data freshness**
   - Look at the `last_updated` attribute on sensors
   - Compare with website's last update time

4. **Clear and restart**
   - Remove the integration
   - Restart Home Assistant
   - Re-add the integration with fresh API key
