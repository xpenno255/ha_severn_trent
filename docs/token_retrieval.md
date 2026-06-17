# Yorkshire Water Portal Capture Notes

Yorkshire Water endpoint support is still being discovered. This page is for development captures only; it is not a stable user setup guide yet.

## What To Capture

After logging in to the Yorkshire Water portal, use browser developer tools to identify:

- Authentication flow and token/session lifetime
- Whether requests use an `Authorization` header, cookies, CSRF tokens, or OAuth
- Account/customer discovery requests
- Meter discovery requests
- Current consumption or current meter reading requests
- Daily usage requests
- Monthly or custom-period usage requests, if present

## Safety

- Do not share raw authorization headers, cookies, session tokens, customer references, account IDs, or meter IDs.
- Redact sensitive values before opening GitHub issues.
- Do not commit captured responses containing personal data.
- Prefer sharing request/response schemas with fake IDs and representative numeric values.

## Useful Debugging

Enable Home Assistant debug logging:

```yaml
logger:
  default: info
  logs:
    custom_components.yorkshire_water: debug
```

The integration redacts known sensitive fields from its own debug logs, but browser captures are not automatically redacted.
