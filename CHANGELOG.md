# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.8.0] - 2026-05-22

### Fixed
- **Critical Fix**: DateTime double-timezone bug causing all smart meter API calls to fail with 400 errors
  - Timezone-aware datetimes formatted with `.isoformat() + "Z"` produced invalid format like `2026-05-22T00:00:00+00:00Z`
  - The Kraken API rejected these with `DateTime cannot represent value` error
  - Added `_api_dt()` helper function that correctly formats both timezone-aware and naive datetimes
  - Affected: smart meter daily/monthly readings, manual meter readings, and meter details queries
- **Critical Fix**: MONETARY sensor state class mismatch causing HA warnings
  - Changed `SensorStateClass.MEASUREMENT` → `SensorStateClass.TOTAL` for all 5 financial sensors
  - HA requires `TOTAL` or `None` for `SensorDeviceClass.MONETARY`; `MEASUREMENT` is invalid
  - Affected sensors: Balance, Overdue Balance, Payment Amount, Outstanding Payment, Next Payment Amount
- **Fix**: Blocking `requests.Session()` creation in HA event loop
  - Changed from eager initialization in `__init__` to lazy property
  - Prevents HA warning about blocking calls in the event loop
- **Fix**: Replaced all `datetime.utcnow()` calls with `datetime.now(timezone.utc)` (5 occurrences)
  - `datetime.utcnow()` is deprecated in Python 3.12+
  - Prevents `DeprecationWarning` errors when running with `-W error::DeprecationWarning`
- **Fix**: Invalid `ReadingFrequencyType` enum value in daily readings retry
  - Changed `"DAY"` → `"DAILY"` to match the Kraken GraphQL schema
  - The API returned `400 Bad Request: Value 'DAY' does not exist in 'ReadingFrequencyType' enum`
  - This caused the retry fallback to fail when `DAY_INTERVAL` returned no data

### Added
- **New Sensor**: `sensor.severn_trent_overdue_balance` – Shows overdue account balance separately
- **New Sensor**: `sensor.severn_trent_smart_meter_status` – Diagnostic sensor showing smart meter data availability
- **New Field**: `overdueBalance` added to `BALANCE_QUERY` GraphQL query
- **New Tests**: 4 tests for `_api_dt()` datetime formatting helper (total: 116 tests)

### Changed
- Balance sensor now includes `overdue_balance_gbp` and `overdue_balance_pence` as extra state attributes
- Added `_attr_has_entity_name = True` to base sensor for proper HA entity naming
  - Entity names are now relative to device name (e.g. "Balance" instead of "Severn Trent Balance")
  - HA displays as "Severn Trent Water (A-1234A123) Balance" — no more redundant "Severn Trent" prefix
  - New sensors get clean entity IDs like `sensor.severn_trent_overdue_balance` instead of long prefixed IDs
  - Existing entity IDs are preserved by HA (no breaking change for automations)

### [1.5.2] - 2026-01-20
-- bump version to fix an issue with home asisstant

## [1.5.1] - 2026-01-18
- Update user documentation for retrival of the authenticaiton token from chrome dev tools

## [1.5.0] - 2026-01-17
- Thanks to @RobXYZ the sensors are now part of a meter device.

## [1.4.1] - 2026-01-17

### Fixed
- **Critical Fix**: Previous week sensor now shows correct values
  - Fixed data fetching to include complete previous week (Monday-Sunday)
  - Previously only fetched last 7 days, missing start of previous week when viewed mid-week
  - Now fetches from previous Monday onwards to ensure all weekly data is available
  - Resolves issue where previous week showed ~30% of actual usage
- **Critical Fix**: Estimated meter reading calculation now includes correct months
  - Fixed monthly period inclusion logic to compare against actual official reading date
  - When official reading is on 1st of month: compares monthly start dates against the official reading date (not month boundary)
  - When official reading is mid-month: excludes that month (partial month covered by daily data)
  - Prevents including historical months before the official reading
  - Added deduplication of monthly readings (API returns duplicate entries per month)
  - Now keeps only the last/most accurate reading for each month
  - Resolves issue where estimated reading was too high (was including 8 duplicate entries instead of 4 unique months)
  - For Oct 1st, 2025 official reading: now correctly includes only Oct, Nov, Dec 2025, Jan 2026 (4 periods)
- **Fix**: Removed invalid state class from Daily Average sensor
  - Removed `MEASUREMENT` state class which is incompatible with `WATER` device class
  - Sensor now correctly represents an average rate without statistics tracking
  - Resolves Home Assistant warning about impossible state class configuration
- **Critical Fix**: Changed from hourly to daily data fetching to match website behavior
  - Now uses `DAY_INTERVAL` instead of `HOUR_INTERVAL` for daily readings
  - Eliminates potential data discrepancies from hourly aggregation
  - Matches exact API behavior used by Severn Trent website
  - Should resolve remaining value mismatches between integration and website
- **Critical Fix**: Yesterday's usage now shows correct date
  - Changed from using most recent date in response to calculating yesterday as (today - 1 day)
  - Matches website behavior which explicitly fetches data for yesterday's date
  - Resolves issue where today's partial data was shown instead of yesterday's complete day

## [1.4.0] - 2026-01-17

### Breaking Changes
- **Removed** `sensor.severn_trent_weekly_total` (replaced with week-to-date sensor)
  - Users will need to update any automations, dashboards, or scripts that reference this sensor
  - Replace with `sensor.severn_trent_week_to_date` or `sensor.severn_trent_previous_week`

### Added
- **New Sensor**: `sensor.severn_trent_week_to_date` - Shows water consumption from Monday to present in the current week
  - Attributes include: `week_start`, `days_in_week`
  - Updates daily as new data becomes available
  - Uses Monday as the start of the week
- **New Sensor**: `sensor.severn_trent_previous_week` - Shows total water consumption for the previous complete week (Monday-Sunday)
  - Attributes include: `week_start`, `week_end`, `days_in_week`
  - Perfect for weekly comparisons and tracking
- Added `device_class` to all water consumption sensors for proper Home Assistant integration
- Enhanced logging with warnings for invalid measurement values

### Fixed
- **Critical Fix**: Corrected state classes for proper Home Assistant long-term statistics
  - `sensor.severn_trent_yesterday_usage` now uses `TOTAL_INCREASING` instead of `TOTAL`
  - `sensor.severn_trent_daily_average` now uses correct unit of measurement
  - All sensors now properly integrate with Home Assistant's Energy Dashboard
- **Critical Fix**: Improved estimated meter reading calculation to prevent double-counting
  - If official reading is mid-month (e.g., Oct 15th), now fetches daily data from that date to end of month
  - Uses monthly data only for complete months after the official reading month
  - Previously could double-count water usage from partial months
- **Critical Fix**: Replaced string-based date comparisons with proper datetime comparisons
  - More robust and prevents edge cases with different date formats
  - Added proper error handling for invalid date formats
- Removed hardcoded unit string formatting (no more `"m³/d"` strings)
- Improved error handling throughout with specific warning messages instead of silent failures

### Changed
- Updated API to accept official reading date parameter for smarter data fetching
- Data coordinator now fetches manual readings first, then uses official date for smart meter queries
- Enhanced estimated meter reading attributes to show both daily and monthly periods included
- Updated estimation note to reflect new calculation method

### Technical Improvements
- Better separation of concerns between daily and monthly data handling
- Reduced API calls while maintaining accuracy
- More detailed debug logging for troubleshooting
- Improved data validation with proper exception handling

## [1.3.0] - 2024-XX-XX

### Changed
- Switched authentication to a browser token → API key flow
- Added re-authentication support for refreshing the API key

## [1.2.0] - 2024-XX-XX

### Added
- Added estimated current meter reading sensor
- Fetches monthly usage data (past 12 months) for accurate estimation
- Improved calculation: official reading + monthly totals (including partial current month)

## [1.1.0] - 2024-XX-XX

### Added
- Added automatic discovery of account numbers
- Added automatic discovery of meter identifiers
- Simplified setup to just email and password
- Added support for multiple accounts
- Added manual meter reading sensor with historical data

## [1.0.0] - 2024-XX-XX

### Added
- Initial release
- Smart meter daily usage tracking
- 7-day average and weekly total sensors
- Integration with Severn Trent Kraken API
- Home Assistant config flow setup

[1.4.0]: https://github.com/xpenno255/ha_severn_trent/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/xpenno255/ha_severn_trent/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/xpenno255/ha_severn_trent/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/xpenno255/ha_severn_trent/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/xpenno255/ha_severn_trent/releases/tag/v1.0.0
