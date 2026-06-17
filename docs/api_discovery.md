# Yorkshire Water API Discovery

Yorkshire Water endpoint support depends on safe browser capture from the live customer portal. Capture only the request and response structure needed to implement the integration. Do not share real account, customer, meter, address, token, cookie, or session values.

## Capture Needed

Use browser DevTools Network captures while signed in to the Yorkshire Water portal. Capture the portal loading, account selection, meter views, and any usage or reading screens that show current, daily, monthly, or period usage.

Useful browser steps:

1. Open a private or temporary browser profile.
2. Sign in to the Yorkshire Water portal.
3. Open DevTools -> Network.
4. Enable Preserve log.
5. Filter to Fetch/XHR requests first.
6. Reload the portal and visit pages that show account, property, meter, consumption, and meter reading data.
7. For each relevant request, copy only the redacted details listed below.
8. If exporting HAR, redact it before sharing.

## Calls To Look For

Look for requests that appear to handle:

- Authentication, session, bootstrap, or user profile setup
- Account or property discovery
- Meter discovery
- Current consumption
- Daily consumption
- Monthly or period usage, if available
- Meter reading, if available

Names may differ in the portal. Prefer evidence from request paths, request bodies, response JSON keys, and the UI action that triggered the request.

## Discovered Route Patterns

Initial redacted captures show an OAuth Authorization Code with PKCE login flow. Do not share real authorization codes, code verifiers, access tokens, refresh tokens, ID tokens, cookies, or session identifiers.

Token exchange:

```json
{
  "method": "POST",
  "endpoint": "https://login.yorkshirewater.com/connect/token",
  "content_type": "application/x-www-form-urlencoded",
  "request_body_shape": {
    "client_id": "css-onlineaccount-fe",
    "grant_type": "authorization_code",
    "redirect_uri": "https://my.yorkshirewater.com/account/callback/response",
    "code": "CODE-REDACTED",
    "code_verifier": "CODE-VERIFIER-REDACTED"
  }
}
```

Smart meter API base:

```text
https://my.yorkshirewater.com/api/account/smartmeter
```

Observed smart meter calls:

```json
[
  {
    "route_name": "meter_details",
    "method": "GET",
    "endpoint_path": "/meter-details",
    "query_parameters": {
      "accountReference": "ACCOUNT-REDACTED"
    },
    "auth": "Authorization: Bearer TOKEN-REDACTED"
  },
  {
    "route_name": "current_consumption",
    "method": "GET",
    "endpoint_path": "/current-consumption",
    "query_parameters": {
      "meterReference": "METER-REDACTED"
    },
    "auth": "Authorization: Bearer TOKEN-REDACTED"
  },
  {
    "route_name": "daily_consumption",
    "method": "GET",
    "endpoint_path": "/daily-consumption",
    "query_parameters": {
      "meterReference": "METER-REDACTED",
      "startDate": "REDACTED",
      "endDate": "REDACTED",
      "moveInDate": "REDACTED",
      "moveOutDate": "REDACTED",
      "timePeriod": "REDACTED"
    },
    "auth": "Authorization: Bearer TOKEN-REDACTED"
  },
  {
    "route_name": "your_usage",
    "method": "GET",
    "endpoint_path": "/your-usage",
    "query_parameters": {
      "meterReference": "METER-REDACTED"
    },
    "auth": "Authorization: Bearer TOKEN-REDACTED"
  }
]
```

No browser cookies are required by the integration scaffold at this stage. Only add cookie handling later if redacted response testing proves the bearer token is insufficient.

## Captured Response Schemas

Redacted token responses include `id_token`, `access_token`, `expires_in`, `token_type`, and `scope`. Parser code must not log or expose raw token values; it should keep only token presence and expiry metadata until auth storage is designed.

Redacted meter discovery responses have been captured with:

```json
{
  "accountReference": "ACCOUNT-REDACTED",
  "meterReference": "METER-REDACTED",
  "startDate": "2099-06-25T00:00:00",
  "endDate": "0001-01-01T00:00:00",
  "currentDate": "2099-06-17T00:00:00+00:00"
}
```

Treat sentinel dates such as `0001-01-01T00:00:00` as unset.

Account summary responses contain useful account status metadata, but they may also contain sensitive billing, payment, address, and postcode data. The integration should expose only safe account status fields by default and must not expose address, postcode, balance, payment plan, payment amounts, or direct debit details.

Daily consumption responses are fetched from `/daily-consumption` with query parameter names `meterReference`, `startDate`, `endDate`, `moveInDate`, `moveOutDate`, and `timePeriod`. Redact all query values before sharing captures. The response contains `dailyUsageData` rows plus totals such as `totalLitres`, tariff cost totals, and daily averages. Redact every `meterReference` value inside response rows.

## Fields To Record

For each candidate call, record exactly these fields:

- HTTP method
- Endpoint path only
- Query parameter names only, with all values replaced by `REDACTED`
- Request body shape, with all values replaced by `REDACTED`
- Response JSON structure, with fake values
- Status code
- Content type

Example format:

```json
{
  "method": "GET",
  "endpoint_path": "/example/usage/daily",
  "query_parameters": {
    "accountId": "REDACTED",
    "meterId": "REDACTED",
    "from": "REDACTED",
    "to": "REDACTED"
  },
  "request_body_shape": null,
  "response_json_structure": {
    "items": [
      {
        "date": "2099-01-01",
        "usage": 123.45,
        "unit": "litres"
      }
    ]
  },
  "status_code": 200,
  "content_type": "application/json"
}
```

## What Not To Share

Never share:

- `Authorization`
- `Cookie`
- Bearer tokens
- Session IDs
- Account numbers
- Customer IDs
- Meter serial numbers
- Address
- Postcode
- Email address
- Full URLs if they contain tokens or session IDs

When in doubt, replace the value with `REDACTED` or use an obviously fake value such as `ACCOUNT-REDACTED`, `CUSTOMER-REDACTED`, or `METER-REDACTED`.
