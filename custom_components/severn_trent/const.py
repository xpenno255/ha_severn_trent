"""Constants for the Severn Trent Water integration."""

DOMAIN = "severn_trent"

API_URL = "https://api.st.kraken.tech/v1/graphql/"

CONF_API_KEY = "api_key"
CONF_BROWSER_TOKEN = "browser_token"
CONF_ACCOUNT_NUMBER = "account_number"
CONF_MARKET_SUPPLY_POINT_ID = "market_supply_point_id"
CONF_DEVICE_ID = "device_id"
CONF_CAPABILITY_TYPE = "capability_type"

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

BALANCE_QUERY = """
query GetBalance($accountNumber: String!) {
  account(accountNumber: $accountNumber) {
    balance
  }
}
"""

RATE_LIMIT_QUERY = """
query apiRateLimitInfo {
  rateLimitInfo {
    pointsAllowanceRateLimit {
      isBlocked
      limit
      remainingPoints
      ttl
      usedPoints
    }
  }
}
"""

PAYMENT_SCHEDULE_QUERY = """
query CurrentActivePaymentSchedule($accountNumber: String!) {
  account(accountNumber: $accountNumber) {
    paymentSchedules(active: true, first: 1) {
      edges {
        node {
          id
          paymentDay
          paymentAmount
          paymentFrequency
          paymentFrequencyMultiplier
          isVariablePaymentAmount
          validTo
          scheduleType
          paymentPlan {
            id
            status
            payments {
              amount
              payableDate
            }
          }
        }
      }
    }
  }
}
"""

METER_DETAILS_QUERY = """
query MeterDetails($accountNumber: String!, $excludeHeld: Boolean = true, $first: Int = 50, $activeFrom: DateTime) {
  account(accountNumber: $accountNumber) {
    properties(activeFrom: $activeFrom) {
      activeWaterMeters {
        id
        serialNumber
        numberOfDigits
        readings(first: $first, excludeHeld: $excludeHeld, excludeQuarantined: true) {
          edges {
            node {
              valueCubicMetres
              readingDate
              source
              id
              isHeld
            }
          }
        }
      }
    }
  }
}
"""

OUTSTANDING_PAYMENT_QUERY = """
query OutstandingPayment($accountNumber: String!) {
  account(accountNumber: $accountNumber) {
    ledgers {
      paymentsOutstanding
    }
  }
}
"""

LEDGERS_QUERY = """
query Ledgers($accountNumber: String!) {
  account(accountNumber: $accountNumber) {
    ledgers {
      number
      ledgerType
    }
  }
}
"""

PAYMENT_FORECAST_QUERY = """
query PaymentForecast($accountNumber: String!, $ledgerNumber: String, $first: Int!) {
  account(accountNumber: $accountNumber) {
    paginatedPaymentForecast(ledgerNumber: $ledgerNumber, first: $first) {
      edges {
        node {
          date
          amount
        }
      }
    }
  }
}
"""