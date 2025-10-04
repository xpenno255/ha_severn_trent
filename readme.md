# Severn Trent Water - Home Assistant Integration

A custom Home Assistant integration for monitoring water usage from Severn Trent smart meters via the Kraken API.

## Features

- **Fully Automatic Setup**: Just enter your email and password - account and meter details are discovered automatically
- **Yesterday's Usage**: Track your water consumption from the previous day
- **7-Day Average**: Monitor your average daily water usage over the past week
- **Weekly Total**: See your total water consumption for the last 7 days
- **Meter Reading**: Official cumulative meter readings with historical data and usage between readings
- **Automatic Updates**: Data refreshes every hour
- **Native Home Assistant Integration**: Full support for Home Assistant's sensor platform with proper units and device classes

## Requirements

- Home Assistant 2025.7 or newer
- A Severn Trent online account with smart meter
- Your account email and password

## Installation

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

Setup is fully automatic! You only need:

1. **Email**: Your Severn Trent account email
2. **Password**: Your Severn Trent account password

The integration will automatically:
- Discover your account number(s)
- Fetch your meter identifiers (Device ID and Market Supply Point ID)
- Set up all sensors with historical data

### Multiple Accounts

If you have multiple Severn Trent accounts, you'll be prompted to select which one to monitor after entering your credentials.

### Setup Process

1. Add the integration through the Home Assistant UI
2. Enter your email and password
3. If you have multiple accounts, select the one to monitor
4. Click Submit

The integration will authenticate and begin fetching your water usage data immediately.

## Sensors

The integration creates four sensors:

| Sensor | Description | Unit |
|--------|-------------|------|
| `sensor.severn_trent_yesterday_usage` | Water consumed yesterday | m³ |
| `sensor.severn_trent_daily_average` | Average daily usage over 7 days | m³/d |
| `sensor.severn_trent_weekly_total` | Total usage over 7 days | m³ |
| `sensor.severn_trent_meter_reading` | Official cumulative meter reading | m³ |

### Sensor Attributes

Each sensor includes additional attributes:

**Yesterday Usage:**
- Date
- Meter ID

**Daily Average:**
- Recent daily readings (last 7 days)
- Period information

**Weekly Total:**
- Period
- Number of days included

**Meter Reading:**
- Reading date
- Reading source (METER_READER, OPS, CUSTOMER)
- Previous reading and date
- Usage since last reading
- Days between readings
- Average daily usage between readings
- All historical readings

## Data Sources

The integration uses two data sources:

1. **Smart Meter Hourly Data**: Automated readings taken every hour, aggregated into daily totals for the past 7 days
2. **Manual Meter Readings**: Official readings taken periodically (typically bi-annually) showing cumulative meter totals

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

If you see "Unauthorized" or authentication errors:
- Verify your email and password are correct
- Check that you can log into the Severn Trent website with the same credentials
- Ensure there are no leading or trailing spaces in your credentials

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
- Provides hourly water usage data from smart meters
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
- Data is aggregated from hourly readings into daily totals

**Manual Meter Readings:**
- Typically taken bi-annually by meter readers
- Shows cumulative meter total (like an odometer)
- Historical readings available for usage tracking over time

## Energy Dashboard Integration

The weekly total sensor can be added to Home Assistant's Energy Dashboard:
1. Go to Settings → Dashboards → Energy
2. Add Water Consumption
3. Select `sensor.severn_trent_weekly_total`

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
