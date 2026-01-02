# Severn Trent Water - Home Assistant Integration

A custom Home Assistant integration for monitoring water usage from Severn Trent smart meters via the Kraken API.

## Features

- **Magic Link Authentication**: Secure authentication using one-time login links sent to your email
- **Automatic Token Refresh**: JWT tokens refresh automatically every 15 minutes
- **Re-authentication Flow**: Seamless re-authentication when tokens expire
- **Yesterday's Usage**: Track your water consumption from the previous day
- **7-Day Average**: Monitor your average daily water usage over the past week
- **Weekly Total**: See your total water consumption for the last 7 days
- **Meter Reading**: Official cumulative meter readings with historical data and usage between readings
- **Estimated Current Meter Reading**: Accurate estimate of your current meter position based on official reading + monthly usage
- **Automatic Updates**: Data refreshes every hour
- **Fully Async**: Non-blocking HTTP calls using aiohttp for optimal Home Assistant performance
- **Native Integration**: Full support for Home Assistant's sensor platform with proper units and device classes

## Requirements

- Home Assistant 2025.1 or newer
- A Severn Trent online account with smart meter
- Your Severn Trent account email address
- Access to your email to receive magic link authentication

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

### Initial Setup

The integration uses a **magic link authentication** flow for secure access:

1. **Add the integration** through the Home Assistant UI (Settings → Devices & Services → Add Integration)
2. **Enter your email**: Provide your Severn Trent account email address
3. **Check your email**: You'll receive a magic link from Severn Trent
4. **Paste the magic link**: Copy the entire URL from the email and paste it into Home Assistant
   - The link looks like: `https://my-account.stwater.co.uk/?key=...`
   - Or you can paste just the 64-character token
5. **Select account** (if you have multiple): Choose which Severn Trent account to monitor
6. **Done**: The integration will automatically discover your meter details and begin fetching data

### Multiple Accounts

If you have multiple Severn Trent accounts, you'll be prompted to select which one to monitor after entering the magic link.

### Re-authentication

When your authentication expires (typically after ~30 minutes of inactivity), Home Assistant will:
1. Display a notification: "Integration requires re-authentication"
2. Click the notification or go to the integration settings
3. Click **"Re-authenticate"**
4. The integration will send a new magic link to your email
5. Paste the new magic link to restore access

## How It Works

### Authentication Flow

1. **Magic Link Request**: Integration sends a request to Severn Trent API
2. **Email Delivery**: You receive an email with a one-time login link
3. **Token Exchange**: Magic link token is exchanged for a JWT (valid 15 min) + refresh token (valid ~30 min)
4. **Automatic Refresh**: JWT tokens refresh automatically in the background
5. **Re-auth on Expiry**: When refresh token expires, you'll be prompted to re-authenticate

### Token Management

- **JWT Token**: Refreshes automatically every 14 minutes (expires after 15 min)
- **Refresh Token**: Valid for ~30 minutes from authentication
- **Stored Securely**: Tokens are stored in Home Assistant's encrypted config storage
- **No Passwords Stored**: Only refresh tokens are stored, never passwords

## Sensors

The integration creates five sensors:

| Sensor | Description | Unit |
|--------|-------------|------|
| `sensor.severn_trent_yesterday_usage` | Water consumed yesterday | m³ |
| `sensor.severn_trent_daily_average` | Average daily usage over 7 days | m³/d |
| `sensor.severn_trent_weekly_total` | Total usage over 7 days | m³ |
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

**Estimated Meter Reading:**
- Last official reading and date
- Usage accumulated since official reading
- Days since official reading
- Number of monthly periods included
- Estimation note

## How the Estimated Meter Reading Works

The estimated meter reading provides an accurate prediction of your current meter position:

1. Starts with your last official meter reading (taken every ~6 months by Severn Trent)
2. Adds monthly usage totals from your smart meter since that date
3. Includes partial data for the current incomplete month

**Example:**
- Official reading: 272 m³ (October 1st, 2025)
- September usage: 9.841 m³
- October usage so far: 0.831 m³
- Estimated current reading: 272 + 9.841 + 0.831 = 282.672 m³

This gives you an accurate running total between official 6-monthly readings.

## Data Sources

The integration uses three data sources from the Severn Trent API:

1. **Smart Meter Hourly Data**: Automated readings taken every hour, aggregated into daily totals for the past 7 days
2. **Smart Meter Monthly Data**: Monthly usage totals for the past 12 months (includes partial current month)
3. **Manual Meter Readings**: Official readings taken periodically (typically bi-annually) showing cumulative meter totals

## Troubleshooting

### Authentication Issues

**Magic link not working:**
- Check your email spam folder
- Ensure you're using the full URL from the email
- Magic links expire quickly - request a new one if needed
- Try pasting just the 64-character token instead of the full URL

**Re-authentication required:**
- This is normal after ~30 minutes of inactivity
- Click the notification and follow the re-authentication flow
- New magic link will be sent to your email

### No Data Showing

1. Check the Home Assistant logs (Settings → System → Logs)
2. Filter for "severn_trent" to see integration-specific messages
3. Manually trigger an update:
   ```yaml
   service: homeassistant.update_entity
   target:
     entity_id: sensor.severn_trent_yesterday_usage
   ```

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
- Requires JWT authentication via magic link
- Provides hourly, daily, and monthly water usage data from smart meters
- Provides manual meter readings with historical data
- JWT tokens expire after 15 minutes (automatically refreshed)
- Refresh tokens expire after ~30 minutes (triggers re-authentication)

## Technical Details

### Architecture

- **Fully Async**: Uses `aiohttp` for all HTTP requests - no blocking operations
- **Token Management**: Automatic JWT refresh with proper error handling
- **Config Flow**: Modern Home Assistant config flow with reauth support
- **Data Coordinator**: Updates every hour using Home Assistant's DataUpdateCoordinator
- **Error Handling**: Graceful degradation with clear error messages

### Update Frequency

By default, the integration updates every hour. Smart meter data has a processing delay, so:
- Yesterday is the most recent complete day available
- Today's data is not available due to API limitations
- Hourly readings are aggregated into daily totals

## Energy Dashboard Integration

The weekly total sensor can be added to Home Assistant's Energy Dashboard:
1. Go to Settings → Dashboards → Energy
2. Add Water Consumption
3. Select `sensor.severn_trent_weekly_total`

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

## Privacy & Security

- **No Passwords Stored**: Only refresh tokens are stored
- **Encrypted Storage**: Tokens stored in Home Assistant's encrypted config
- **Magic Link Security**: One-time use links that expire quickly
- **Local Processing**: All data stays within your Home Assistant instance
- **No Third-Party Services**: Direct communication with Severn Trent API only

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

### v2.0.0 (Major Update)
- **BREAKING**: Switched to magic link authentication (email/password no longer supported)
- Fully async implementation using aiohttp
- Automatic JWT token refresh every 15 minutes
- Re-authentication flow when tokens expire
- Improved error handling and logging
- Better Home Assistant integration practices

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
