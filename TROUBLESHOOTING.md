# Troubleshooting

## Sensors Are Unavailable

The Yorkshire Water API layer is currently a development scaffold. If logs say the daily consumption endpoint is not configured, the integration loaded correctly but live Yorkshire Water endpoint details still need to be implemented.

## Authentication Errors

The temporary config flow accepts a portal session or access token while discovery is in progress. If Home Assistant asks for reauthentication, paste a fresh token from a current Yorkshire Water portal session.

Do not post raw tokens, cookies, account IDs, customer references, or meter IDs in support requests.

## Enable Debug Logging

```yaml
logger:
  default: info
  logs:
    custom_components.yorkshire_water: debug
```

The integration redacts common sensitive fields in its own debug output.

## Useful Issue Details

When reporting issues, include:

- Home Assistant version
- Integration version
- Which sensors are unavailable
- Redacted debug logs
- Redacted request/response schema from the Yorkshire Water portal, if testing API discovery

Avoid screenshots or captures that reveal personal account data.
