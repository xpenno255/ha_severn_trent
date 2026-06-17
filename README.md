# Yorkshire Water - Home Assistant Integration

A custom Home Assistant integration for Yorkshire Water smart meter usage.

This integration is being adapted for Yorkshire Water's customer portal. The Home Assistant integration identity and architecture are in place, and the provider-specific API layer is isolated for Yorkshire Water endpoint discovery.

## Current Status

- Home Assistant domain: `yorkshire_water`
- Component folder: `custom_components/yorkshire_water`
- Integration name: Yorkshire Water
- Repository: `https://github.com/Crash-Evans/ha_yorkshire_water`
- API status: beta manual bearer token mode for captured smart meter endpoints; full OAuth PKCE login is not implemented yet

This is a new Home Assistant integration/domain. Add Yorkshire Water as a fresh integration.

## Sensors

The initial Yorkshire Water sensor set is intentionally practical:

| Sensor | Entity ID pattern | Unit |
| --- | --- | --- |
| Yesterday Usage | `sensor.yorkshire_water_yesterday_usage` | L |
| Today Usage | `sensor.yorkshire_water_today_usage` | L |
| 7-Day Average | `sensor.yorkshire_water_7_day_average` | L |
| Week to Date | `sensor.yorkshire_water_week_to_date` | L |
| Previous Week | `sensor.yorkshire_water_previous_week` | L |
| Month to Date | `sensor.yorkshire_water_month_to_date` | L |
| Year to Date | `sensor.yorkshire_water_year_to_date` | L |
| Meter Reading | `sensor.yorkshire_water_meter_reading` | m³ |
| Estimated Cumulative Usage | `sensor.yorkshire_water_estimated_cumulative_usage` | m³ |
| Continuous Flow Alarm | `sensor.yorkshire_water_continuous_flow_alarm` | diagnostic |
| Data Latest Update Status | `sensor.yorkshire_water_data_latest_update_status` | diagnostic |
| Status | `sensor.yorkshire_water_status` | diagnostic |

Usage values are normalized to litres. Attributes include source period start/end, latest data date, latest update date, estimated and missing day counts, available cost breakdown fields, raw period data when available, data freshness, and whether the meter reading is estimated.

If the temporary bearer token or required account/meter references are missing, the integration stays in endpoint discovery mode and exposes a status message instead of making live requests.

## Home Assistant Energy Dashboard

Home Assistant's Energy Dashboard water section needs a cumulative water sensor with `device_class: water` and `state_class: total_increasing`. Period sensors such as Yesterday Usage, Week to Date, Month to Date, and Year to Date are useful for daily monitoring, but they reset or change with the reporting period and should not be added to the Energy Dashboard.

Use `sensor.yorkshire_water_estimated_cumulative_usage` for Energy Dashboard water consumption. It reports cubic metres and is estimated from the usage totals available from Yorkshire Water, not from an official physical meter-reading endpoint. If a later API response contains less usage than a previous refresh, the integration preserves the previous cumulative value so the sensor remains monotonic.

To add it, open Settings -> Dashboards -> Energy -> Water consumption, then select Estimated Cumulative Usage.

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

The current config flow is a temporary beta development flow. It accepts either:

- A raw temporary `access_token` from a current Yorkshire Water portal session
- The full token response JSON from DevTools, containing `access_token`, `id_token`, `expires_in`, `token_type`, and `scope`
- Optional account reference
- Optional meter reference

This is not a full OAuth login. Access tokens expire quickly and must be refreshed manually until OAuth PKCE login and refresh handling are implemented. If you paste the full token response JSON, the integration stores the `access_token` for temporary API use and records a safe expiry timestamp so it can report `token_expired` instead of making doomed API calls. The `id_token` is ignored for API calls.

If you provide an account reference but not a meter reference, the integration tries to discover the meter reference from the smart meter meter-details endpoint. If you provide neither reference, the integration remains in endpoint discovery mode.

The integration stores the temporary access token only in the Home Assistant config entry for now and redacts it in integration logs. Do not paste access tokens, ID tokens, full token responses, account references, meter references, cookies, screenshots, or raw portal captures into GitHub issues or logs.

## API Discovery Notes

Yorkshire Water beta support currently uses these captured smart meter endpoints with bearer-token auth:

- `GET /api/account/smartmeter/meter-details?accountReference=...`
- `GET /api/account/smartmeter/current-consumption?meterReference=...`
- `GET /api/account/smartmeter/your-usage?meterReference=...`

The API client has async request helpers, structured errors, safe redacted debug logging, and parser scaffolding for captured response schemas.

Sensitive values redacted from debug logs include authorization headers, cookies, tokens, customer references, account IDs, and meter IDs.

See [docs/api_discovery.md](docs/api_discovery.md) and [docs/redaction_checklist.md](docs/redaction_checklist.md) before sharing any captured request or response structure.

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

## History

Historical changelog entries and license attribution are retained where appropriate, but user-facing integration branding is now Yorkshire Water.
