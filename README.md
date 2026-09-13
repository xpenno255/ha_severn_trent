# Severn Trent Water - Home Assistant Integration

A custom Home Assistant integration for monitoring water usage from Severn Trent smart meters via the Kraken API.

## Features

- **Guided Setup**: Paste a temporary browser token to generate an API key, and account/meter details are discovered automatically
- **Yesterday's Usage**: Track your water consumption from the previous day
- **7-Day Average**: Monitor your average daily water usage over the past week
- **Week to Date**: See your water consumption from Monday to present in the current week
- **Previous Week**: View your total water consumption for the previous week (Monday-Sunday)
- **Meter Reading**: Official cumulative meter readings with historical data and usage between readings
- **Estimated Current Meter Reading**: Estimate based on the official reading + available daily/monthly usage, with checks for missing history
- **Account Balance**: Current account balance and overdue balance
- **Payment Information**: Direct debit amount, next payment date, and outstanding payments
- **Smart Meter Diagnostics**: Meter ID, capability type, API rate limit status, and smart meter data availability
- **Automatic Updates**: Data refreshes every hour
- **Native Home Assistant Integration**: Full support for Home Assistant's sensor platform with proper units and device classes

## Requirements

- Home Assistant 2026.9 or newer (v1.9.0 uses the current recorder statistics API)
- A Severn Trent online account
- A temporary Authorization token from your Severn Trent browser session

> **Note:** Daily usage sensors (yesterday, average, week-to-date, previous week) require a smart meter. Accounts with only manual meters will still see balance, payment, and meter reading sensors.

> **v1.8.0**: This release fixes **three critical bugs** that were causing smart meter sensors to show "unavailable":
> 1. **DateTime double-timezone bug** — all API calls with datetime parameters were sending invalid format like `2026-05-22T00:00:00+00:00Z`, causing 400 errors
> 2. **Invalid ReadingFrequencyType enum** — the daily readings retry used `"DAY"` instead of the correct `"DAILY"` enum value
> 3. **MONETARY state class mismatch** — financial sensors used `MEASUREMENT` instead of `TOTAL`, preventing long-term statistics
>
> It also fixes a blocking call warning and adopts modern HA entity naming (`has_entity_name`). If your smart meter sensors were unavailable, upgrade to this version.

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
           ├── statistics.py
           ├── diagnostics.py
           ├── strings.json
           └── translations/
   ```

2. Restart Home Assistant

3. Go to Settings → Devices & Services → Add Integration

4. Search for "Severn Trent Water"

## Configuration

Setup accepts an existing API key, a browser Authorization token, or a configured connection to reuse. Browser-token instructions are below; reusing a connection avoids rotating its key.

The integration will automatically:
- Discover your account number(s)
- Fetch your meter identifiers (Device ID and Market Supply Point ID)
- Set up all sensors with historical data

### Multiple Accounts

If you have multiple Severn Trent accounts, you'll be prompted to select which one to monitor after entering your credentials.

### Setup Process

1. Add the integration through the Home Assistant UI
2. Reuse an existing connection, enter an API key, or paste a browser Authorization token
3. If you have multiple accounts, select the one to monitor
4. Select a meter when prompted and submit

The integration will authenticate and begin fetching your water usage data immediately.

### Getting the Browser Authorization Token

See the [Token Retrieval Guide](docs/token_retrieval.md) for detailed instructions with screenshots.

## Sensors

The integration creates 22 sensors (Usage pattern is disabled by default) grouped into a single device per account:

### Water Usage Sensors

| Sensor | Description | Unit | Category |
|--------|-------------|------|----------|
| `sensor.severn_trent_yesterday_usage` | Water consumed yesterday | m³ | — |
| `sensor.severn_trent_daily_average` | Average daily usage over 7 days | m³ | — |
| `sensor.severn_trent_week_to_date` | Water consumed this week (Mon–present) | m³ | — |
| `sensor.severn_trent_previous_week` | Water consumed last week (Mon–Sun) | m³ | — |
| `sensor.severn_trent_meter_reading` | Official cumulative meter reading | m³ | — |
| `sensor.severn_trent_estimated_meter_reading` | Estimated current meter reading | m³ | — |

### Financial Sensors

| Sensor | Description | Unit | Category |
|--------|-------------|------|----------|
| `sensor.severn_trent_balance` | Current account balance | GBP | — |
| `sensor.severn_trent_overdue_balance` | Overdue account balance | GBP | — |
| `sensor.severn_trent_payment_amount` | Direct debit payment amount | GBP | — |
| `sensor.severn_trent_outstanding_payment` | Outstanding payment amount | GBP | — |
| `sensor.severn_trent_next_payment_amount` | Next scheduled payment amount | GBP | — |
| `sensor.severn_trent_next_payment_date` | Next scheduled payment date | date | — |

### Diagnostic Sensors

| Sensor | Description | Unit | Category |
|--------|-------------|------|----------|
| `sensor.severn_trent_meter_digits` | Number of digits on the meter | — | Diagnostic |
| `sensor.severn_trent_latest_reading_meta` | Latest reading metadata (ID, source, date) | — | Diagnostic |
| `sensor.severn_trent_market_supply_point_id` | Market Supply Point ID | — | Diagnostic |
| `sensor.severn_trent_device_id` | Meter device/serial number | — | Diagnostic |
| `sensor.severn_trent_meter_capability` | Meter capability type (e.g. SMART_METER) | — | Diagnostic |
| `sensor.severn_trent_api_rate_limit_remaining` | API rate limit points remaining | points | Diagnostic |
| `sensor.severn_trent_smart_meter_status` | Smart meter data availability status | — | Diagnostic |

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

**Balance:**
- Balance in pence
- Overdue balance in GBP and pence

**Overdue Balance:**
- Overdue balance in pence

**Payment Amount:**
- Schedule ID
- Payment amount in pence
- Payment day, frequency, and frequency multiplier
- Whether the amount is variable
- Valid-to date and schedule type

**Smart Meter Status:**
- Whether smart meter data is available
- Whether manual meter data is available
- Individual field values (yesterday_usage, daily_average, etc.)
- Meter ID
- Monthly and daily readings counts
- Reason for unavailability (if applicable)

## How the Estimated Meter Reading Works

The estimated meter reading combines your official reading with available consumption. It is not a live meter reading: current-month totals may be partial or delayed. Missing daily or monthly periods make the estimate unavailable, with the missing periods listed in its attributes. A zero official reading is valid.

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

This gives an estimate between official readings when the required history is present. It may change downwards when Severn Trent corrects readings; those corrections are not treated as meter replacements.

### Calendar periods and missing data

Daily and weekly calculations use `Europe/London`, including British Summer Time. The 7-day average covers exactly the seven completed calendar days ending yesterday. It is unavailable until all seven dates have valid readings. Weekly totals also remain unavailable when an expected day is missing; the attributes show days received and days expected. On Monday, week-to-date is zero because no day in the new week has completed.

## Data Sources

The integration uses multiple API endpoints:

1. **Smart Meter Daily Data**: Automated readings aggregated into daily totals for the past 2+ weeks (covers current and previous week)
2. **Smart Meter Monthly Data**: Monthly usage totals for the past 12 months (used for estimated meter reading)
3. **Manual Meter Readings**: Official readings taken periodically (typically bi-annually) showing cumulative meter totals
4. **Account Balance**: Current balance and overdue balance
5. **Payment Schedule**: Direct debit/payment plan details
6. **Meter Details**: Meter configuration (digits, serial number)
7. **Rate Limit Info**: API rate limit status and remaining points
8. **Ledgers**: Account ledger information (for identifying water accounts)
9. **Payment Forecast**: Next upcoming payment

## Troubleshooting

### Smart Meter Sensors Show "Unavailable"

If `yesterday_usage`, `daily_average`, `week_to_date`, or `previous_week` show as **unavailable**, check the `sensor.severn_trent_smart_meter_status` diagnostic sensor:

| Status | Meaning |
|--------|---------|
| `ok` | Smart meter data is available with daily readings |
| `manual_only` | Only manual meter readings available — your account may not have a smart meter |
| `no_daily_data` | Smart meter data exists but daily readings aren't available |
| `stale_data` | Daily history exists, but yesterday's reading is missing |
| `incomplete_data` | Yesterday is present, but a weekly period has missing readings |
| `error` | No data returned from the API at all |

Common causes:
- **No smart meter**: If your account only has a manual meter, daily usage sensors will be unavailable. The official meter reading still works. The estimate requires consumption history covering the period since that reading.
- **API rate limiting**: Check `sensor.severn_trent_api_rate_limit_remaining` — if `is_blocked` is `true`, wait for the rate limit to reset.
- **Incorrect meter identifiers**: Try reconfiguring the integration to rediscover meter details.

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
- "Yesterday" means the preceding UK calendar day; missing readings are unavailable, not zero
- "Today" data is not available due to API limitations
- Hourly data is aggregated into daily totals
- Monthly data includes partial data for incomplete months

**Manual Meter Readings:**
- Typically taken bi-annually by meter readers
- Shows cumulative meter total (like an odometer)
- Historical readings available for usage tracking over time

## Energy Dashboard Integration

In **Settings → Dashboards → Energy → Water consumption**, select **Severn Trent daily water (your meter serial)**. This is an external statistic, not a sensor entity. The **Water history status** diagnostic sensor exposes its exact `statistic_id` and import progress.

Use one source per physical meter. When switching from Yesterday Usage or Week to Date, remove that old water source from the dashboard to avoid double counting. The integration does not change dashboard settings or erase existing statistics automatically.

The first refresh imports the latest 35 days and begins a one-year backfill in 31-day windows. Each hourly refresh checks recent readings and one older window; a year normally takes about 12 successful refreshes. Older windows are revisited to pick up corrections. Saved dated readings survive restarts, and corrected cumulative totals are reimported at the same timestamps. Missing supplier days are not invented; check `missing_recent_days` before relying on completeness.

Consumption is assigned to its original **Europe/London calendar day**, including BST changes. Since the supplier supplies daily totals, the whole day's usage appears in its final hour. This is a daily accounting convention, **not an hourly usage profile**. Home Assistant downtime does not shift imported usage onto the restart date. History remains limited to readings Severn Trent actually supplies.

Existing Yesterday Usage, Week to Date and Previous Week sensors retain their entity IDs and now declare explicit period resets. This prevents false negative reset consumption (#30), including equal totals in successive periods. Those entity histories still record when data arrives, so the dated external statistic is the recommended Energy source. Existing negative statistics are not automatically repaired: back up first and review affected entries in **Developer Tools → Statistics** if retaining an old source.

### Freshness, diagnostics and unusual usage

- **Latest daily reading** shows the newest completed supplier date.
- **Water history status** shows import progress, missing recent days and the Energy statistic ID.
- Download diagnostics from the integration menu for coverage and availability information; credentials, account numbers, meter IDs and financial amounts are excluded.
- **Usage pattern** is disabled by default. Enable it on the integration's device if wanted, and use state `elevated` in an automation. It requires all 31 completed days: each of the latest three must exceed both 0.5 m³ and twice the preceding 28-day average. Missing yesterday or an incomplete baseline gives `insufficient_data`. This is delayed consumption monitoring, not a real-time leak detector.
- Balance attributes explicitly distinguish `credit`, `debit`, and `settled`, with separate credit and amount-owed values in GBP.

### Accounts and authentication

Setup accepts an existing API key, a browser Authorization token, or another configured connection to reuse. Choose the account and, where necessary, its meter. Reuse credentials when adding another account: generating a key from a browser token rotates the supplier user's key and may invalidate keys used by other software. Reauthentication verifies account access and updates other configured accounts that share the old key.

Connection failures are retried; rejected credentials start Home Assistant's reauthentication flow. Meter details and water ledger metadata are cached for 24 hours; restarting/reloading clears these caches.

### Known supplier limitation

The official-reading endpoint is deprecated but still works. A live test on 13 September 2026 found that the advertised `POINT_IN_TIME` replacement returns `Unsupported aggregation interval`; unaggregated measurements return interval consumption, not official cumulative readings. Version 1.9.0 retains the working official-reading endpoint. Daily Energy statistics use the supported measurements API independently. Estimated meter readings remain estimates and become unavailable if required history is missing.

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

### v1.8.0

**Critical Fixes:**
- Fixed DateTime double-timezone bug causing all smart meter API calls to fail with 400 errors
  - Added `_api_dt()` helper to correctly format timezone-aware datetimes for the Kraken API
  - Previously produced invalid format like `2026-05-22T00:00:00+00:00Z`
- Fixed invalid `ReadingFrequencyType` enum value in daily readings retry (`"DAY"` → `"DAILY"`)
- Skip `DAILY` retry for VISUAL/MANUAL meters (they don't support daily aggregation)
- Fixed MONETARY sensor state class mismatch (`MEASUREMENT` → `TOTAL`) for all 5 financial sensors
- Fixed blocking `requests.Session()` creation in HA event loop (now uses lazy `@property`)
- Fixed `datetime.utcnow()` deprecation (5 occurrences → `datetime.now(timezone.utc)`)

**New Sensors:**
- `sensor.severn_trent_overdue_balance` — Shows overdue account balance separately
- `sensor.severn_trent_smart_meter_status` — Diagnostic sensor showing smart meter data availability

**Changes:**
- Added `overdueBalance` field to balance query
- Balance sensor now includes `overdue_balance_gbp` and `overdue_balance_pence` attributes
- Added `_attr_has_entity_name = True` for proper HA entity naming (cleaner entity IDs)
- 116 tests passing (4 new tests for `_api_dt()` helper)

### v1.7.0
- Added overdue balance sensor (`sensor.severn_trent_overdue_balance`)
- Added smart meter status diagnostic sensor (`sensor.severn_trent_smart_meter_status`)
- Added next payment amount and date sensors
- Added outstanding payment sensor
- Added meter digits and latest reading metadata diagnostic sensors
- Added API rate limit remaining diagnostic sensor
- Added market supply point ID, device ID, and capability type diagnostic sensors
- Added payment amount sensor (direct debit details)
- Fixed `datetime.utcnow()` deprecation — all datetime calls now use `datetime.now(timezone.utc)`
- Improved diagnostic logging for smart meter data availability
- Better error messages when smart meter data is unavailable
- Updated README with full sensor documentation

### v1.5.2
-- bump version to fix an issue with home assistant

### v1.5.1
-- Update user docs to help explain the authentication token retrieval process

### v1.5.0
-- Thanks to @RobXYZ the sensors are now part of a meter device.

### v1.4.1
- **Critical Fix**: Previous week sensor now shows correct values
  - Fixed data fetching to cover complete previous week
  - Resolves issue where weekly usage was under-reported

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
- Added re-authentication support for refreshing the API key

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

## Development checks

The regression tests use real Home Assistant classes and its statistics compiler, with mocked network and database access. The current test target is Home Assistant 2026.9.2 on Python 3.14.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-test.txt
.venv/bin/python -m pytest tests/ -q
.venv/bin/python scripts/validate_schema.py
```

Schema validation performs anonymous, read-only introspection against Severn Trent. It verifies query structure; account permissions and actual values still require a signed-in comparison.
