# Yorkshire Water - Home Assistant Integration

A custom Home Assistant integration for Yorkshire Water smart meter usage.

This integration is being adapted for Yorkshire Water's customer portal. The Home Assistant integration identity and architecture are in place, and the provider-specific API layer is isolated for Yorkshire Water endpoint discovery.

## Current Status

- Home Assistant domain: `yorkshire_water`
- Component folder: `custom_components/yorkshire_water`
- Integration name: Yorkshire Water
- Repository: `https://github.com/Crash-Evans/ha_yorkshire_water`
- API status: beta manual bearer token mode plus experimental OAuth PKCE token exchange foundation for captured smart meter endpoints

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
| Yesterday Cost | `sensor.yorkshire_water_yesterday_cost` | GBP |
| Today Cost | `sensor.yorkshire_water_today_cost` | GBP |
| Week to Date Cost | `sensor.yorkshire_water_week_to_date_cost` | GBP |
| Previous Week Cost | `sensor.yorkshire_water_previous_week_cost` | GBP |
| Month to Date Cost | `sensor.yorkshire_water_month_to_date_cost` | GBP |
| Year to Date Cost | `sensor.yorkshire_water_year_to_date_cost` | GBP |
| Continuous Flow Alarm | `sensor.yorkshire_water_continuous_flow_alarm` | diagnostic |
| Data Latest Update Status | `sensor.yorkshire_water_data_latest_update_status` | diagnostic |
| Status | `sensor.yorkshire_water_status` | diagnostic |

Usage values are normalized to litres. Attributes include source period start/end, latest data date, latest update date, estimated and missing day counts, available cost breakdown fields, raw period data when available, data freshness, and whether the meter reading is estimated.

If the temporary bearer token or required account/meter references are missing, the integration stays in endpoint discovery mode and exposes a status message instead of making live requests.

## Home Assistant Energy Dashboard

Home Assistant's Energy Dashboard water section needs a cumulative water sensor with `device_class: water` and `state_class: total_increasing`. Period sensors such as Yesterday Usage, Week to Date, Month to Date, and Year to Date are useful for daily monitoring, but they reset or change with the reporting period and should not be added to the Energy Dashboard.

Use `sensor.yorkshire_water_estimated_cumulative_usage` for Energy Dashboard water consumption. It reports cubic metres and is estimated from the usage totals available from Yorkshire Water, not from an official physical meter-reading endpoint. If a later API response contains less usage than a previous refresh, the integration preserves the previous cumulative value so the sensor remains monotonic.

To add it, open Settings -> Dashboards -> Energy -> Water consumption, then select Estimated Cumulative Usage.

## Cost Tracking

Cost sensors are separate from the Energy Dashboard water usage sensor. Home Assistant's Energy Dashboard should use the cumulative water sensor in m³, while the cost sensors are normal monetary sensors in GBP for Lovelace cards, reports, and dashboards.

Yorkshire Water currently provides clean water, sewerage, and total cost values in the captured daily and monthly/yearly usage payloads. The integration exposes period total cost sensors for yesterday, today, week to date, previous week, month to date, and year to date, with clean water and sewerage breakdowns retained as attributes where available.

These values are portal and tariff estimates. They may differ from final bill calculations after billing adjustments, tariff changes, rounding, or account-specific charges.

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

The current config flow is a beta development flow. It accepts:

- A raw temporary `access_token` from a current Yorkshire Water portal session
- The full token response JSON from DevTools, containing `access_token`, `id_token`, `expires_in`, `token_type`, and `scope`
- Experimental OAuth PKCE token-exchange inputs: authorization code or callback URL, plus the matching PKCE code verifier
- Optional account reference
- Optional meter reference

Access tokens expire quickly, typically after about 900 seconds. If you paste the full token response JSON, the integration stores the `access_token` for temporary API use and records a safe expiry timestamp so it can report `token_expired` or `refresh_unavailable` instead of making doomed API calls. The `id_token` is ignored for API calls.

The OAuth PKCE foundation can exchange an authorization code at `https://login.yorkshirewater.com/connect/token` using the captured Yorkshire Water client ID and redirect URI. A fully automated browser login is not implemented yet because the authorization URL flow still needs more redacted portal capture. If Yorkshire Water includes a `refresh_token` in a token response, the integration stores it and attempts silent refresh before smart meter requests. If no `refresh_token` is present, reauthentication is required when the access token expires.

The captured Yorkshire Water website scope is `openid user-names css-onlineaccount-api css-registration-api`. It does not currently include `offline_access`, which likely explains why no `refresh_token` has been observed. The code includes an experimental scope builder for controlled testing with `offline_access`, but it is not enabled by default. If Yorkshire Water rejects that scope, the integration treats it as `offline_access_not_supported` without exposing secrets.

To test refresh-token support experimentally without deleting the integration, open Settings -> Devices & Services -> Yorkshire Water -> Configure, choose the experimental OAuth/PKCE auth update mode, and tick Experimental: request offline access / refresh token. Open the generated authorization URL, complete the Yorkshire Water login, then paste the final callback URL or authorization code back into Home Assistant with the matching PKCE code verifier. If the token exchange succeeds, check `sensor.yorkshire_water_status` for `refresh_available: true`. Other possible outcomes are `offline_access_not_supported`, or OAuth succeeds but `refresh_available` remains false because Yorkshire Water still did not issue a refresh token.

In current beta mode, `token_expired` or `reauth_required` is expected after the roughly 15-minute access token lifetime unless Yorkshire Water starts issuing a refresh token. Open the Yorkshire Water integration entry in Settings -> Devices & Services and use the reauthentication prompt to paste a fresh full token response JSON or raw access token. A fresh token response updates the stored access token and expiry timestamp, reloads the integration, and sensors should recover without deleting and re-adding Yorkshire Water.

If you provide an account reference but not a meter reference, the integration tries to discover the meter reference from the smart meter meter-details endpoint. If you provide neither reference, the integration remains in endpoint discovery mode.

The integration stores only the access token, optional refresh token, safe expiry timestamp, and configured account or meter references in the Home Assistant config entry. It redacts secrets in integration logs. Do not paste access tokens, ID tokens, refresh tokens, authorization codes, code verifiers, full token responses, account references, meter references, cookies, screenshots, or raw portal captures into GitHub issues or logs.

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
