# Redaction Checklist

Before sharing any Yorkshire Water portal capture, check every section below.

## Headers

- [ ] Remove `Authorization`.
- [ ] Remove `Cookie`.
- [ ] Remove CSRF, session, request verification, and correlation tokens if they identify a session.
- [ ] Keep only non-sensitive header names and generic content negotiation values when needed.

## Cookies

- [ ] Remove all cookie values.
- [ ] Remove session cookie names if they are unique to your account or session.
- [ ] Do not share browser cookie screenshots.

## Tokens

- [ ] Remove bearer tokens.
- [ ] Remove access tokens.
- [ ] Remove refresh tokens.
- [ ] Remove ID tokens.
- [ ] Remove one-time codes, state values, nonce values, and session IDs.

## Account Identifiers

- [ ] Replace account numbers with `ACCOUNT-REDACTED`.
- [ ] Replace customer IDs with `CUSTOMER-REDACTED`.
- [ ] Replace property IDs with `PROPERTY-REDACTED`.
- [ ] Replace billing references with `ACCOUNT-REDACTED`.

## Meter Identifiers

- [ ] Replace meter IDs with `METER-REDACTED`.
- [ ] Replace meter serial numbers with `METER-REDACTED`.
- [ ] Replace smart meter identifiers with `METER-REDACTED`.

## Personal Details

- [ ] Remove names.
- [ ] Remove addresses.
- [ ] Remove postcodes.
- [ ] Remove email addresses.
- [ ] Remove phone numbers.

## Request URLs

- [ ] Share endpoint paths only, not full URLs.
- [ ] Replace every query parameter value with `REDACTED`.
- [ ] Remove URLs containing tokens, sessions, codes, or signed parameters.

## Request Bodies

- [ ] Preserve JSON key names only when useful.
- [ ] Replace every value with `REDACTED` unless it is a generic fake value.
- [ ] Remove nested account, customer, meter, address, postcode, email, token, and session values.

## Response Bodies

- [ ] Replace real values with fake values.
- [ ] Preserve enough JSON structure to show object names, arrays, field names, and value types.
- [ ] Replace account, customer, property, and meter identifiers.
- [ ] Replace readings and dates with fake examples.

## Screenshots

- [ ] Crop out names, addresses, account numbers, meter serials, and postcodes.
- [ ] Blur portal profile menus and account switchers.
- [ ] Blur browser address bars if URLs include sensitive values.
- [ ] Prefer redacted JSON text over screenshots when possible.

## HAR Exports

- [ ] Redact before attaching or committing.
- [ ] Remove all cookies and authorization headers.
- [ ] Remove full URLs containing sensitive query values.
- [ ] Replace request and response body values with fake values.
- [ ] Check the HAR with a text search for your name, email, postcode, address, account number, and meter serial.
