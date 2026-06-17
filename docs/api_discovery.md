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
