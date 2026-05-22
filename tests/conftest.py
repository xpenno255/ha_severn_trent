"""Shared fixtures for Severn Trent API tests."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to sys.path so we can import custom_components directly
# without needing homeassistant installed
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Mock homeassistant modules before importing any custom_components
# so that __init__.py imports don't fail
for mod in [
    "homeassistant",
    "homeassistant.config_entries",
    "homeassistant.const",
    "homeassistant.core",
    "homeassistant.exceptions",
    "homeassistant.helpers",
    "homeassistant.helpers.update_coordinator",
]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

from custom_components.severn_trent.api import SevernTrentAPI
from custom_components.severn_trent.const import API_URL


# ---------------------------------------------------------------------------
# Mock responses
# ---------------------------------------------------------------------------

def _make_response(json_data: dict, status_code: int = 200) -> MagicMock:
    """Create a mock requests.Response object."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    mock.raise_for_status = MagicMock()
    if status_code >= 400:
        mock.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return mock


@pytest.fixture
def api() -> SevernTrentAPI:
    """Return an API instance with test credentials."""
    return SevernTrentAPI(
        api_key="test-api-key",
        account_number="1234567890",
        market_supply_point_id="MSP123",
        device_id="DEV456",
        capability_type="SMART_METER",
    )


@pytest.fixture
def authenticated_api(api: SevernTrentAPI) -> SevernTrentAPI:
    """Return an API instance that is already authenticated."""
    api.token = "test-jwt-token"
    api.refresh_token = "test-refresh-token"
    api.token_expires_at = 9999999999  # far in the future
    return api


# ---------------------------------------------------------------------------
# Sample GraphQL responses
# ---------------------------------------------------------------------------

AUTH_SUCCESS_RESPONSE = {
    "data": {
        "obtainKrakenToken": {
            "token": "jwt-token-abc123",
            "payload": {},
            "refreshToken": "refresh-token-xyz",
            "refreshExpiresIn": 86400,
        }
    }
}

AUTH_ERROR_RESPONSE = {
    "errors": [{"message": "Invalid credentials"}]
}

ACCOUNT_LIST_RESPONSE = {
    "data": {
        "viewer": {
            "accounts": [
                {"number": "1234567890"},
                {"number": "0987654321"},
            ]
        }
    }
}

METER_IDENTIFIERS_RESPONSE = {
    "data": {
        "account": {
            "properties": [
                {
                    "activeWaterMeters": [
                        {
                            "meterPointReference": "MSP123",
                            "serialNumber": "DEV456",
                            "capabilityType": "SMART_METER",
                        }
                    ]
                }
            ]
        }
    }
}

SMART_METER_DAILY_RESPONSE = {
    "data": {
        "account": {
            "properties": [
                {
                    "measurements": {
                        "edges": [
                            {
                                "node": {
                                    "startAt": "2026-05-20T00:00:00Z",
                                    "endAt": "2026-05-21T00:00:00Z",
                                    "value": 0.15,
                                    "unit": "m³",
                                    "readAt": "2026-05-20T23:59:59Z",
                                }
                            },
                            {
                                "node": {
                                    "startAt": "2026-05-19T00:00:00Z",
                                    "endAt": "2026-05-20T00:00:00Z",
                                    "value": 0.12,
                                    "unit": "m³",
                                    "readAt": "2026-05-19T23:59:59Z",
                                }
                            },
                        ]
                    }
                }
            ]
        }
    }
}

SMART_METER_MONTHLY_RESPONSE = {
    "data": {
        "account": {
            "properties": [
                {
                    "measurements": {
                        "edges": [
                            {
                                "node": {
                                    "startAt": "2026-04-01T00:00:00Z",
                                    "endAt": "2026-05-01T00:00:00Z",
                                    "value": 4.5,
                                    "unit": "m³",
                                    "readAt": "2026-05-01T00:00:00Z",
                                }
                            },
                        ]
                    }
                }
            ]
        }
    }
}

MANUAL_READINGS_RESPONSE = {
    "data": {
        "account": {
            "properties": [
                {
                    "activeWaterMeters": [
                        {
                            "id": "meter-1",
                            "numberOfDigits": 5,
                            "readings": {
                                "edges": [
                                    {
                                        "node": {
                                            "valueCubicMetres": 1234.5,
                                            "readingDate": "2026-05-01T00:00:00Z",
                                            "source": "CUSTOMER",
                                        }
                                    },
                                    {
                                        "node": {
                                            "valueCubicMetres": 1230.0,
                                            "readingDate": "2026-04-01T00:00:00Z",
                                            "source": "CUSTOMER",
                                        }
                                    },
                                ]
                            },
                        }
                    ]
                }
            ]
        }
    }
}

BALANCE_RESPONSE = {
    "data": {
        "account": {
            "balance": 12345  # £123.45 in pence-like format
        }
    }
}

RATE_LIMIT_RESPONSE = {
    "data": {
        "rateLimitInfo": {
            "pointsAllowanceRateLimit": {
                "isBlocked": False,
                "limit": 1000,
                "remainingPoints": 950,
                "ttl": 3600,
                "usedPoints": 50,
            }
        }
    }
}

PAYMENT_SCHEDULE_RESPONSE = {
    "data": {
        "account": {
            "paymentSchedules": {
                "edges": [
                    {
                        "node": {
                            "id": "sched-1",
                            "paymentDay": 15,
                            "paymentAmount": 2500,  # £25.00
                            "paymentFrequency": "MONTHLY",
                            "paymentFrequencyMultiplier": 1,
                            "isVariablePaymentAmount": False,
                            "validTo": "2026-12-31",
                            "scheduleType": "DIRECT_DEBIT",
                            "paymentPlan": None,
                        }
                    }
                ]
            }
        }
    }
}

METER_DETAILS_RESPONSE = {
    "data": {
        "account": {
            "properties": [
                {
                    "activeWaterMeters": [
                        {
                            "id": "meter-1",
                            "serialNumber": "DEV456",
                            "numberOfDigits": 5,
                            "readings": {
                                "edges": [
                                    {
                                        "node": {
                                            "valueCubicMetres": 1234.5,
                                            "readingDate": "2026-05-01T00:00:00Z",
                                            "source": "CUSTOMER",
                                            "id": "reading-1",
                                            "isHeld": False,
                                        }
                                    }
                                ]
                            },
                        }
                    ]
                }
            ]
        }
    }
}

OUTSTANDING_PAYMENT_RESPONSE = {
    "data": {
        "account": {
            "ledgers": [
                {
                    "paymentsOutstanding": 5000  # £50.00
                }
            ]
        }
    }
}

LEDGERS_RESPONSE = {
    "data": {
        "account": {
            "ledgers": [
                {
                    "number": "LEDGER1",
                    "ledgerType": "SEVERN_TRENT_WATER",
                }
            ]
        }
    }
}

PAYMENT_FORECAST_RESPONSE = {
    "data": {
        "account": {
            "paginatedPaymentForecast": {
                "edges": [
                    {
                        "node": {
                            "date": "2026-06-15",
                            "amount": 2500,  # £25.00
                        }
                    }
                ]
            }
        }
    }
}

API_KEY_GENERATION_RESPONSE = {
    "data": {
        "regenerateSecretKey": {
            "key": "new-api-key-abc123"
        }
    }
}