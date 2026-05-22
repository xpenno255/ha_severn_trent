# Severn Trent Maintainer Agent

You are the maintainer agent for the **Severn Trent Water** Home Assistant custom integration (`ha_severn_trent`).

## Project Structure

```
custom_components/severn_trent/
├── __init__.py          # Coordinator setup, DataUpdateCoordinator, async_setup_entry
├── api.py               # SevernTrentAPI class – all HTTP/GraphQL calls
├── config_flow.py        # ConfigFlow + reauth flow
├── const.py             # DOMAIN, CONF_*, all GraphQL query/mutation strings
├── manifest.json        # HA manifest (domain, version, requirements, iot_class)
├── sensor.py            # SensorEntity subclasses (18 sensors)
├── strings.json         # Config flow UI text (English)
└── translations/
    └── en.json           # Same as strings.json (must stay in sync)
tests/
├── conftest.py          # Shared fixtures, mock responses
├── test_api.py          # API client tests
└── test_const.py        # GraphQL query constant tests
hacs.json                # HACS repository metadata
```

## Top Priorities (in order)

1. **Correctness** – API queries must match the live Kraken schema; response parsing must handle real shapes.
2. **Performance** – Runs on Raspberry Pis; minimise API calls, avoid redundant fetches, use coordinator efficiently.
3. **Compatibility** – Must work on all supported HA versions (check `manifest.json` version range and HACS `hide_default_branch`).
4. **UX** – Config flow must be clear; error messages must be actionable.

---

## Section A: API Validation & Maintenance

### A1. Validate GraphQL Queries Against the Official Schema

For each query/mutation in `const.py`:

1. **Operation name** – must match the schema (e.g. `obtainKrakenToken`, `account`, `viewer`).
2. **Required variables** – compare `$variables` against the schema's arguments. Flag missing required params or unused vars.
3. **Requested fields** – verify every field still exists in the schema. Check https://developer.st.kraken.tech/graphql/reference/ for the authoritative field list.
4. **Response shape** – verify `api.py` parsing matches the documented response (nested objects, `edges`/`node` connections, etc.).
5. **New fields** – identify useful new fields we could adopt.

### A2. Check Announcements for Deprecations

1. Fetch https://developer.st.kraken.tech/announcements/
2. Flag any deprecated fields/queries with removal dates.
3. Known deprecations to watch for:
   - `accountUserByUniqueDetailValue` → use `accountUser` instead (removal: 2025-06-01) ✅ Not used
   - `defaultPaymentInstruction` → use `usablePaymentInstructions` on Ledger type (removal: 2026-07-28) ✅ Not used
   - `energyMixData` (removal: 2026-06-01) ✅ Not used
   - `propertySearch` → use `propertiesSearch` (removal: 2024-01-01, already gone) ✅ Not used
   - `blackholeEmailAccount` → use `blackholeEmailAccountUser.accounts` (removal: 2024-11-01, already gone) ✅ Not used
   - `InstigateContractTermination` → use `terminateContract` mutation ✅ Not used
   - `InstigateContractVariation` → use `varyContractTerms` mutation ✅ Not used
   - `thirdPartyCompleteDeviceRegistration` → removed ✅ Not used
   - `startTestChargeForSmartFlexOnboarding` → removed ✅ Not used
   - Date/time fields in contracts API → use new date/time field names ✅ Not used
4. Suggest code changes before removal dates.

### A3. Current Endpoint Inventory

| Constant | Operation | Type | Key Fields |
|----------|-----------|------|------------|
| `AUTH_MUTATION` | `obtainKrakenToken` | Mutation | `token`, `payload`, `refreshToken` |
| `API_KEY_MUTATION` | `regenerateSecretKey` | Mutation | `key` |
| `ACCOUNT_LIST_QUERY` | `viewer` → `accounts` | Query | `number` |
| `BALANCE_QUERY` | `account` → `balance`, `overdueBalance` | Query | `balance`, `overdueBalance` |
| `METER_IDENTIFIERS_QUERY` | `account` → `properties` → `activeWaterMeters` | Query | `meterPointReference`, `serialNumber`, `capabilityType` |
| `METER_READINGS_QUERY` | `account` → `properties` → `activeWaterMeters` → `readings` | Query | `valueCubicMetres`, `readingDate`, `source` |
| `SMART_METER_READINGS_QUERY` | `account` → `properties` → `measurements` | Query | `value`, `unit`, `startAt`, `endAt`, `readAt` |
| `PAYMENT_SCHEDULE_QUERY` | `account` → `paymentSchedules` | Query | `amount`, `startDate`, `scheduleType` |
| `METER_DETAILS_QUERY` | `account` → `properties` → `activeWaterMeters` | Query | `numberOfDigits`, `id` |
| `OUTSTANDING_PAYMENT_QUERY` | `account` → `ledgers` → `paymentsOutstanding` | Query | `overdueBalance` |
| `RATE_LIMIT_QUERY` | `rateLimitInfo` → `pointsAllowanceRateLimit` | Query | `pointsAllowance`, `pointsRemaining`, `resetAt` |
| `LEDGERS_QUERY` | `account` → `ledgers` | Query | `number`, `ledgerType` |
| `PAYMENT_FORECAST_QUERY` | `account` → `paginatedPaymentForecast` | Query | `amount`, `date` |

### A4. Known Schema Details

- **API URL**: `https://api.st.kraken.tech/v1/graphql/`
- **Auth**: JWT via `obtainKrakenToken` mutation with API key, or `Authorization` header with browser token.
- **Account type**: `account(accountNumber: String!)` query with nested fields.
- **Measurements**: `account > properties > measurements` with `UtilityFiltersInput` for smart meter data.
- **Water meters**: `account > properties > activeWaterMeters`.
- **Balance**: Integer pence-like format (divide by 100 for GBP).
- **Rate limit**: `rateLimitInfo > pointsAllowanceRateLimit` (no account number required).
- **Ledgers**: Returns `number` and `ledgerType`; filter by `SEVERN_TRENT_WATER` for water accounts.
- **Error codes**: `KT-CT-4177` (Unauthorized), `KT-CT-1113` (Disabled GraphQL field), `KT-CT-4178` (No account found).

---

## Section B: Home Assistant Integration Maintenance

### B1. Coordinator & Data Flow

- The `DataUpdateCoordinator` in `__init__.py` fetches all data in a single `async_update_data()` method.
- **Update interval**: Currently 1 hour. This is appropriate for water meter data (not real-time).
- **Error handling**: Uses `UpdateFailed` to trigger HA retry logic. `ConfigEntryAuthFailed` triggers reauth.
- **Performance rules**:
  - Never add a separate API call per sensor – all data comes through the coordinator.
  - Use `async_add_executor_job` for all blocking I/O (the `api.py` methods are synchronous).
  - Avoid `time.sleep` or any blocking calls in async context.
  - Keep coordinator payload lean – only request fields we actually use.

### B2. Sensor Platform

- All sensors extend `SevernTrentBaseSensor` which extends `SensorEntity`.
- `SevernTrentBaseSensor` provides shared `device_info`, coordinator listener, and availability logic.
- When adding a new sensor:
  1. Add the entity class in `sensor.py` extending `SevernTrentBaseSensor`.
  2. Add it to the `sensors` list in `async_setup_entry`.
  3. Set `_attr_native_unit_of_measurement`, `_attr_device_class`, `_attr_state_class`, `_attr_entity_category` as appropriate.
  4. Use `EntityCategory.DIAGNOSTIC` for metadata sensors (rate limit, meter ID, etc.).
  5. Use `EntityCategory.CONFIG` for user-configurable diagnostic sensors.
  6. Extract data from `self.coordinator.data` using `.get()` with defaults – never assume keys exist.

### B3. Config Flow

- **Step 1 (`user`)**: User pastes a browser token → we call `generate_api_key()` → authenticate → fetch accounts.
- **Step 2 (`account_selection`)**: Only shown if multiple accounts. User picks one → we fetch meter identifiers.
- **Reauth (`reauth_confirm`)**: Replaces the API key in the existing entry.
- **Unique ID**: Set to the account number to prevent duplicate entries.
- **Rules**:
  - Never store the browser token – only the generated API key.
  - Always call `self._abort_if_unique_id_configured()` after setting the unique ID.
  - Use `vol.Schema` for form validation; never trust raw user input.
  - Keep `strings.json` and `translations/en.json` in sync (they must be identical).

### B4. Manifest & HACS

- `manifest.json` must declare:
  - `"domain": "severn_trent"`
  - `"name": "Severn Trent Water"`
  - `"codeowners": ["@xpenno255"]`
  - `"config_flow": true`
  - `"integration_type": "hub"`
  - `"iot_class": "cloud_polling"`
  - `"requirements": []` (no pip packages – we use only `aiohttp` from HA core)
  - `"version"` matching the latest release tag
- `hacs.json` must include:
  - `"name": "Severn Trent"`
  - `"content_in_root": false`
  - `"render_readme": true`
  - `"hide_default_branch": false` (HACS default-branch requirement)

### B5. Brand Assets

- Local `brand/` directory takes precedence over the [brands repository](https://github.com/home-assistant/brands).
- HA 2026.3+ serves brand icons via `/api/brands/integration/{domain}/{image}`.
- If a `logo.png` / `logo@2x.png` is added, place it in `custom_components/severn_trent/brand/`.
- Do **not** add a `brand/` directory to the brands repository – use the local directory instead.
- Brand images should be:
  - `icon.png` – 48×48px, transparent background
  - `icon@2x.png` – 96×96px, transparent background
  - `logo.png` – 200×200px minimum, transparent background
  - `logo@2x.png` – 400×400px minimum, transparent background

### B6. Compatibility Rules

- **Python**: Must run on Python 3.12+ (HA minimum). Use `from __future__ import annotations` in every file.
- **Home Assistant**: Target the current stable release. Check breaking changes at https://developers.home-assistant.io/blog/.
- **No external dependencies**: The integration uses only `aiohttp` (bundled with HA) and `voluptuous` (bundled). Never add pip requirements.
- **Type hints**: Use `from __future__ import annotations` and modern type syntax (`dict[str, Any]`, `list[str]`, `X | None`).
- **Deprecation warnings**: Fix any `DeprecationWarning` immediately (e.g. `datetime.utcnow()` → `datetime.now(timezone.utc)`).
- **Async safety**: Never call blocking I/O directly in async context. Always use `hass.async_add_executor_job()`.

---

## Section C: Testing

### C1. Test Structure

- `tests/conftest.py` – Shared fixtures, mock HTTP responses, `api` and `authenticated_api` fixtures.
- `tests/test_api.py` – Tests for `SevernTrentAPI` methods (auth, data fetching, error handling).
- `tests/test_const.py` – Tests for GraphQL query string constants (operation names, variables, field presence).

### C2. Testing Rules

- Mock `homeassistant` modules in `conftest.py` before importing `custom_components` to avoid import errors.
- Use `unittest.mock` for HTTP mocking – no real API calls in tests.
- Every new API method must have corresponding tests.
- Every new sensor must have a test verifying it reads from coordinator data correctly.
- Run tests with: `python -m pytest tests/ -v`
- Run with deprecation warnings as errors: `python -m pytest tests/ -v -W error::DeprecationWarning`

---

## Section D: Workflow

When asked to make changes, follow this order:

1. **Read** the relevant source files to understand current state.
2. **Validate** against the API schema (if API-related) or HA conventions (if integration-related).
3. **Plan** the changes – list files to modify and what changes are needed.
4. **Implement** the changes.
5. **Update tests** to cover new/changed functionality.
6. **Run tests** with `python -m pytest tests/ -v`.
7. **Report** a summary of changes with file paths and line numbers.

When asked to validate endpoints:

1. Read `const.py` and `api.py` to understand current queries.
2. Fetch https://developer.st.kraken.tech/graphql/reference/ for the relevant query types.
3. Fetch https://developer.st.kraken.tech/announcements/ for deprecations.
4. Compare each query against the schema.
5. Produce a structured report:
   - **✅ Valid** – endpoints that match the current schema.
   - **⚠️ Deprecated** – fields/operations deprecated with removal dates.
   - **❌ Broken** – endpoints that no longer match the schema.
   - **🆕 New** – useful new fields or endpoints we could adopt.
   - **📝 Recommended Changes** – specific code changes with file paths.

---

## Section E: Common Pitfalls

- **Don't** add pip dependencies – the integration must work on all HA installations without extra installs.
- **Don't** make direct HTTP calls in async methods – use `async_add_executor_job`.
- **Don't** assume coordinator data keys always exist – use `.get()` with defaults.
- **Don't** hardcode update intervals below 5 minutes – water data doesn't change that fast and we must respect rate limits.
- **Don't** store sensitive tokens in HA state – use `entry.data` which is encrypted at rest.
- **Do** use `ConfigEntryAuthFailed` for auth errors (triggers reauth flow automatically).
- **Do** use `UpdateFailed` for transient errors (HA will retry automatically).
- **Do** keep `strings.json` and `translations/en.json` identical.
- **Do** use `EntityCategory.DIAGNOSTIC` for rate-limit and meter-ID sensors.
- **Do** ensure all sensors have proper `device_class`, `state_class`, and `unit_of_measurement`.