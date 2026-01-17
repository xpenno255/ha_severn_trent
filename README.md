# Severn Trent Water - Home Assistant Integration

A custom Home Assistant integration for monitoring water usage from Severn Trent smart meters via the Kraken API.

## Features

- **Guided Setup**: Paste a temporary browser token to generate an API key, and account/meter details are discovered automatically
- **Yesterday's Usage**: Track your water consumption from the previous day
- **7-Day Average**: Monitor your average daily water usage over the past week
- **Week to Date**: See your water consumption from Monday to present in the current week
- **Previous Week**: View your total water consumption for the previous week (Monday-Sunday)
- **Meter Reading**: Official cumulative meter readings with historical data and usage between readings
- **Estimated Current Meter Reading**: Accurate estimate of your current meter position based on official reading + daily/monthly usage
- **Automatic Updates**: Data refreshes every hour
- **Native Home Assistant Integration**: Full support for Home Assistant's sensor platform with proper units and device classes

## Requirements

- Home Assistant 2025.1 or newer
- A Severn Trent online account with smart meter
- A temporary Authorization token from your Severn Trent browser session

## Installation

### HACS Installation (Recommended)

1. Ensure you have [HACS](https://hacs.xyz/) installed in Home Assistant
2. Open HACS in Home Assistant (sidebar)
3. Click the three dots menu in the top right corner
4. Select **"Custom repositories"**
5. Add the repository:
   - **Repository URL**: `https://github.com/xpenno255/ha_severn_trent`
   - **Category**: Integration
6. Click **"Add"**
7. Close the custom repositories dialog
8. Find "Severn Trent Water" in the HACS integration list
9. Click **"Download"**
10. Restart Home Assistant
11. Go to Settings → Devices & Services → **Add Integration**
12. Search for "Severn Trent Water" and follow the setup wizard

### Manual Installation

1. Copy the `severn_trent` folder to your Home Assistant `custom_components` directory:
   ```
   config/
   └── custom_components/
       └── severn_trent/
           ├── __init__.py
           ├── api.py
           ├── config_flow.py
           ├── const.py
           ├── manifest.json
           ├── sensor.py
           └── strings.json
   ```

2. Restart Home Assistant

3. Go to Settings → Devices & Services → Add Integration

4. Search for "Severn Trent Water"

## Configuration

Setup is guided! You only need:

1. **Browser Authorization Token**: Temporary token copied from your browser after logging in

The integration will automatically:
- Discover your account number(s)
- Fetch your meter identifiers (Device ID and Market Supply Point ID)
- Set up all sensors with historical data

### Multiple Accounts

If you have multiple Severn Trent accounts, you'll be prompted to select which one to monitor after entering your credentials.

### Setup Process

1. Add the integration through the Home Assistant UI
2. Paste your browser Authorization token
3. If you have multiple accounts, select the one to monitor
4. Click Submit

The integration will authenticate and begin fetching your water usage data immediately.

### Getting the Browser Authorization Token

1. Log in to the Severn Trent website in your browser
2. Open Developer Tools → Network and find a request to `https://api.st.kraken.tech/v1/graphql/`
3. Copy the `Authorization` header value from that request
4. Paste it into the integration setup form

## Sensors

The integration creates six sensors:

| Sensor | Description | Unit |
|--------|-------------|------|
| `sensor.severn_trent_yesterday_usage` | Water consumed yesterday | m³ |
| `sensor.severn_trent_daily_average` | Average daily usage over 7 days | m³ |
| `sensor.severn_trent_week_to_date` | Water consumed this week (Mon-present) | m³ |
| `sensor.severn_trent_previous_week` | Water consumed last week (Mon-Sun) | m³ |
| `sensor.severn_trent_meter_reading` | Official cumulative meter reading | m³ |
| `sensor.severn_trent_estimated_meter_reading` | Estimated current meter reading | m³ |

### Sensor Attributes

Each sensor includes additional attributes:

**Yesterday Usage:**
- Date
- Meter ID

**Daily Average:**
- Recent daily readings (last 7 days)
- Period information

**Week to Date:**
- Week start date (Monday)
- Number of days in current week so far

**Previous Week:**
- Week start date (Monday)
- Week end date (Sunday)
- Number of days in week (always 7)

**Meter Reading:**
- Reading date
- Reading source (METER_READER, OPS, CUSTOMER)
- Previous reading and date
- Usage since last reading
- Days between readings
- Average daily usage between readings
- All historical readings

**Estimated Meter Reading:**
- Last official reading and date
- Usage accumulated since official reading
- Days since official reading
- Number of daily periods included (partial month)
- Number of monthly periods included (complete months)
- Estimation note

## How the Estimated Meter Reading Works

The estimated meter reading provides an accurate prediction of your current meter position:

1. Starts with your last official meter reading (taken every ~6 months by Severn Trent)
2. If the official reading was taken mid-month, adds daily usage totals from that date to the end of that month
3. Adds monthly usage totals for all complete months after the official reading month
4. This approach prevents double-counting while minimizing API calls

**Example (mid-month reading):**
- Official reading: 272 m³ (October 15th, 2024)
- Daily usage Oct 15-31: 2.5 m³ (partial month - uses daily data)
- November usage: 9.2 m³ (complete month - uses monthly data)
- December usage: 8.8 m³ (complete month - uses monthly data)
- Estimated current reading: 272 + 2.5 + 9.2 + 8.8 = 292.5 m³

**Example (1st of month reading):**
- Official reading: 272 m³ (October 1st, 2024)
- October usage: 9.5 m³ (complete month - uses monthly data)
- November usage: 9.2 m³ (complete month - uses monthly data)
- Estimated current reading: 272 + 9.5 + 9.2 = 290.7 m³

This gives you an accurate running total between official 6-monthly readings.

## Data Sources

The integration uses three data sources:

1. **Smart Meter Hourly Data**: Automated readings taken every hour, aggregated into daily totals for the past 7 days
2. **Smart Meter Monthly Data**: Monthly usage totals for the past 12 months (includes partial current month)
3. **Manual Meter Readings**: Official readings taken periodically (typically bi-annually) showing cumulative meter totals

## Troubleshooting

### No Data Showing

1. Check the Home Assistant logs (Settings → System → Logs)
2. Filter for "severn_trent" to see integration-specific messages
3. Manually trigger an update:
   ```yaml
   service: homeassistant.update_entity
   target:
     entity_id: sensor.severn_trent_yesterday_usage
   ```

### Authentication Errors

If you see authentication errors:
- Ensure the browser token is fresh (it can expire quickly)
- Reopen the Severn Trent website, log in again, and copy a new `Authorization` token
- Make sure you pasted the raw token value (no extra whitespace)

### No Accounts Found

If the integration reports "No Severn Trent accounts found":
- Verify you have an active Severn Trent account
- Check that your account has a smart water meter installed
- Try logging into the Severn Trent website to confirm your account is active

### Enable Debug Logging

Add to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.severn_trent: debug
```

Then restart Home Assistant to see detailed logs.

## API Information

This integration uses the Kraken API platform (developed by Octopus Energy and used by Severn Trent). The API:
- Uses GraphQL for data queries
- Requires JWT authentication
- Provides hourly, daily, and monthly water usage data from smart meters
- Provides manual meter readings with historical data
- Tokens expire after 15 minutes (automatically refreshed)

## Update Frequency

By default, the integration updates every hour. To change this, edit `__init__.py`:

```python
update_interval=timedelta(hours=1),  # Change to desired interval
```

Recommended intervals:
- Hourly: `timedelta(hours=1)` (default)
- Every 6 hours: `timedelta(hours=6)`
- Daily: `timedelta(days=1)`

Note: Smart meter data has a delay - hourly readings aren't available immediately and yesterday's data is the most recent complete day available.

## Data Limitations

**Smart Meter Data:**
- Hourly readings have a processing delay
- "Yesterday" is the most recent complete day available
- "Today" data is not available due to API limitations
- Hourly data is aggregated into daily totals
- Monthly data includes partial data for incomplete months

**Manual Meter Readings:**
- Typically taken bi-annually by meter readers
- Shows cumulative meter total (like an odometer)
- Historical readings available for usage tracking over time

## Energy Dashboard Integration

The water consumption sensors can be added to Home Assistant's Energy Dashboard:
1. Go to Settings → Dashboards → Energy
2. Add Water Consumption
3. Select `sensor.severn_trent_week_to_date` or `sensor.severn_trent_previous_week`

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License.

## Disclaimer

This is an unofficial integration and is not affiliated with or endorsed by Severn Trent. Use at your own risk.

## Acknowledgments

- Built using the Kraken API platform by Octopus Energy
- Thanks to the Home Assistant community
- Special thanks to all contributors who helped discover API endpoints and improve the integration

## Support

For issues, questions, or feature requests, please open an issue on GitHub.

## Changelog

### v1.4.1
- **Critical Fix**: Previous week sensor now shows correct values
  - Fixed data fetching to cover complete previous week
  - Resolves issue where weekly usage was underreported

### v1.4.0
- **Breaking Change**: Replaced "Weekly Total" sensor with "Week to Date" (Monday-present)
- Added new "Previous Week" sensor (Monday-Sunday of last week)
- Fixed state classes for proper Home Assistant statistics integration
- Improved estimated meter reading calculation to prevent double-counting
  - Uses daily data for partial months when official reading is mid-month
  - Uses monthly data only for complete months after official reading
- Enhanced date comparison logic (proper datetime vs string comparison)
- Added device classes to all water consumption sensors
- Improved error handling and validation logging
- All sensors now properly support Home Assistant Energy Dashboard

### v1.3.0
- Switched authentication to a browser token -> API key flow
- Added reauthentication support for refreshing the API key

### v1.2.0
- Added estimated current meter reading sensor
- Fetches monthly usage data (past 12 months) for accurate estimation
- Improved calculation: official reading + monthly totals (including partial current month)

### v1.1.0
- Added automatic discovery of account numbers
- Added automatic discovery of meter identifiers
- Simplified setup to just email and password
- Added support for multiple accounts
- Added manual meter reading sensor with historical data

### v1.0.0
- Initial release
- Smart meter daily usage tracking
- 7-day average and weekly total sensors
