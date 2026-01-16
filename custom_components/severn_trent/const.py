"""Constants for the Severn Trent Water integration."""

DOMAIN = "severn_trent"

API_URL = "https://api.st.kraken.tech/v1/graphql/"

CONF_API_KEY = "api_key"
CONF_BROWSER_TOKEN = "browser_token"
CONF_ACCOUNT_NUMBER = "account_number"
CONF_MARKET_SUPPLY_POINT_ID = "market_supply_point_id"
CONF_DEVICE_ID = "device_id"

AUTH_MUTATION = """
mutation ObtainKrakenToken($input: ObtainJSONWebTokenInput!) {
  obtainKrakenToken(input: $input) {
    token
    payload
    refreshToken
    refreshExpiresIn
  }
}
"""

API_KEY_MUTATION = """
mutation CreateAPIKey {
  regenerateSecretKey {
    key
  }
}
"""

ACCOUNT_LIST_QUERY = """
query AccountNumberList {
  viewer {
    accounts {
      number
    }
  }
}
"""

METER_IDENTIFIERS_QUERY = """
query GetMeterIdentifiers($accountNumber: String!) {
  account(accountNumber: $accountNumber) {
    properties {
      activeWaterMeters {
        meterPointReference
        serialNumber
        capabilityType
      }
    }
  }
}
"""

METER_READINGS_QUERY = """
query MeterReadings($accountNumber: String!, $activeFrom: DateTime) {
  account(accountNumber: $accountNumber) {
    properties(activeFrom: $activeFrom) {
      activeWaterMeters {
        id
        numberOfDigits
        readings(first: 10, excludeHeld: true, excludeQuarantined: true) {
          edges {
            node {
              valueCubicMetres
              readingDate
              source
            }
          }
        }
      }
    }
  }
}
"""

SMART_METER_READINGS_QUERY = """
query SmartMeterReadings($accountNumber: String!, $startAt: DateTime, $endAt: DateTime, $utilityFilters: [UtilityFiltersInput]!) {
  account(accountNumber: $accountNumber) {
    properties {
      measurements(
        first: 1000
        startAt: $startAt
        endAt: $endAt
        utilityFilters: $utilityFilters
      ) {
        edges {
          node {
            ... on IntervalMeasurementType {
              startAt
              endAt
            }
            value
            unit
            readAt
          }
        }
      }
    }
  }
}
"""
