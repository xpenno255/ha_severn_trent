# Yorkshire Water - Home Assistant Integration

A custom Home Assistant integration for Yorkshire Water smart meter usage.

This fork is being adapted from the upstream Severn Trent Water integration, but Yorkshire Water does not appear to use the same Kraken GraphQL API flow. The Home Assistant integration identity and architecture have been renamed, and the provider-specific API layer is now isolated for Yorkshire Water endpoint discovery.

## Current Status

- Home Assistant domain: `yorkshire_water`
- Component folder: `custom_components/yorkshire_water`
- Integration name: Yorkshire Water
- Repository: `https://github.com/Crash-Evans/ha_yorkshire_water`
- API status: development scaffold only; live Yorkshire Water portal endpoints still need to be captured and implemented

This is a new Home Assistant integration/domain. Existing Severn Trent entries are not migrated automatically; add Yorkshire Water as a fresh integration.

## Sensors

The initial Yorkshire Water sensor set is intentionally practical:

| Sensor | Entity ID pattern | Unit |
| --- | --- | --- |
| Yesterday Usage | `sensor.yorkshire_water_yesterday_usage` | m³ |
| Today Usage | `sensor.yorkshire_water_today_usage` | m³ |
| 7-Day Average | `sensor.yorkshire_water_7_day_average` | m³ |
| Week to Date | `sensor.yorkshire_water_week_to_date` | m³ |
| Previous Week | `sensor.yorkshire_water_previous_week` | m³ |
| Meter Reading | `sensor.yorkshire_water_meter_reading` | m³ |
| Status | `sensor.yorkshire_water_status` | diagnostic |

Usage values are normalized to cubic metres. Attributes include source period start/end, raw period data when available, data freshness, and whether the meter reading is estimated.

Until the live Yorkshire Water API contract is implemented, these sensors may be unavailable with a coordinator warning that the daily consumption endpoint is not configured.

## Installation

### HACS

1. Open HACS in Home Assistant.
2. Open the custom repositories dialog.
3. Add `https://github.com/Crash-Evans/ha_yorkshire_water` as an Integration repository.
4. Download Yorkshire Water.
5. Restart Home Assistant.
6. Go to Settings -> Devices & Services -> Add Integration.
7. Search for Yorkshire Water.

### Manual

Copy `custom_components/yorkshire_water` into your Home Assistant `custom_components` directory:

```text
config/
└── custom_components/
    └── yorkshire_water/
        ├── __init__.py
        ├── api.py
        ├── config_flow.py
        ├── const.py
        ├── manifest.json
        ├── sensor.py
        └── strings.json
```

Restart Home Assistant, then add Yorkshire Water from Settings -> Devices & Services.

## Configuration

The current config flow is a temporary development flow. It accepts:

- Portal session or access token
- Optional account ID or customer reference
- Optional meter ID or serial number

The integration stores only the values needed by the config entry. Do not paste tokens into GitHub issues, screenshots, or logs.

## API Discovery Notes

The old Severn Trent Kraken GraphQL queries have been removed from the active integration. Yorkshire Water support needs a live portal capture to confirm:

- Authentication method: OAuth, bearer token, session cookie, CSRF flow, or another mechanism
- Account discovery endpoint
- Meter discovery endpoint
- Current meter reading or current consumption endpoint
- Daily consumption endpoint
- Monthly or period consumption endpoint, if available

The API client already has async request helpers, structured errors, safe redacted debug logging, and normalizers ready to adapt once the endpoint schema is known.

Sensitive values redacted from debug logs include authorization headers, cookies, tokens, customer references, account IDs, and meter IDs.

## Debug Logging

```yaml
logger:
  default: info
  logs:
    custom_components.yorkshire_water: debug
```

Debug logs are designed to be useful during endpoint discovery while redacting sensitive fields.

## Validation

From the repository root:

```bash
python -m compileall custom_components/yorkshire_water
```

If your development environment has Home Assistant tooling installed, also run manifest validation and any configured linter or test suite.

## Upstream Attribution

This fork originated from `xpenno255/ha_severn_trent`. Historical changelog entries and license attribution are retained where appropriate, but user-facing integration branding is now Yorkshire Water.
