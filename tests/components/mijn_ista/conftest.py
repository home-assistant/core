"""Shared fixtures for mijn_ista tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from custom_components.mijn_ista.const import CONF_UPDATE_INTERVAL, DOMAIN

# ---------------------------------------------------------------------------
# Raw API response fixtures
# ---------------------------------------------------------------------------

MOCK_USER_VALUES: dict = {
    "JWT": "refreshed-jwt-token",
    "DisplayName": "Test User",
    "Cus": [
        {
            "Cuid": "test-cuid-abc123",
            "Adress": "Teststraat 1",
            "Zip": "1234 AB",
            "City": "Amsterdam",
            "DateStart": "2020-01-01T00:00:00",
            "curConsumption": {
                "Billingservices": [
                    {
                        "Id": 1,
                        "Description": "Verwarming",
                        "MeterType": "HCA",
                        "Unit": "Gigajoule",
                    },
                    {
                        "Id": 2,
                        "Description": "Warm water",
                        "MeterType": "WW",
                        "Unit": "m3",
                    },
                ],
                "ServicesComp": [
                    {
                        "Id": 1,
                        "TotalNow": 42.5,
                        "TotalPrevious": 48.0,
                        "TotalDiffperc": -11.5,
                        "TotalWholePrevious": 48.0,
                        "DecPos": 1,
                        "CurMeters": [
                            {
                                "MeterId": 101,
                                "serviceId": 1,
                                "MeterNr": 12345,
                                "ArtNr": 0,
                                "BsDate": "2024-01-01T00:00:00",
                                "BeginValue": 0.0,
                                "EsDate": "2024-12-31T00:00:00",
                                "EndValue": 42.5,
                                "CValue": 42.5,
                                "DecPos": 1,
                            }
                        ],
                        "CompMeters": [
                            {
                                "MeterId": 101,
                                "serviceId": 1,
                                "MeterNr": 12345,
                                "ArtNr": 0,
                                "BsDate": "2023-01-01T00:00:00",
                                "BeginValue": 0.0,
                                "EsDate": "2023-12-31T00:00:00",
                                "EndValue": 48.0,
                                "CValue": 48.0,
                                "DecPos": 1,
                            }
                        ],
                    },
                    {
                        "Id": 2,
                        "TotalNow": 18.0,
                        "TotalPrevious": 20.0,
                        "TotalDiffperc": -10.0,
                        "TotalWholePrevious": 20.0,
                        "DecPos": 1,
                        "CurMeters": [
                            {
                                "MeterId": 201,
                                "serviceId": 2,
                                "MeterNr": 67890,
                                "ArtNr": 0,
                                "BsDate": "2024-01-01T00:00:00",
                                "BeginValue": 0.0,
                                "EsDate": "2024-12-31T00:00:00",
                                "EndValue": 18.0,
                                "CValue": 18.0,
                                "DecPos": 1,
                            }
                        ],
                        "CompMeters": [],
                    },
                ],
                "BillingPeriods": [
                    {
                        "y": 2024,
                        "s": "2024-01-01T00:00:00",
                        "e": "2024-12-31T00:00:00",
                        "ta": 10.5,
                    },
                    {
                        "y": 2023,
                        "s": "2023-01-01T00:00:00",
                        "e": "2023-12-31T00:00:00",
                        "ta": 9.8,
                    },
                ],
            },
        }
    ],
}

MOCK_MONTH_VALUES: dict = {
    "JWT": "refreshed-jwt-token",
    "mc": [
        {
            "y": 2024,
            "m": 11,
            "at": 8.2,
            "ServiceConsumptions": [
                {
                    "ServiceId": 1,
                    "TotalConsumption": 4.2,
                    "BuldingAverage": 5.0,
                    "HasApproximation": False,
                    "DeviceConsumptions": [
                        {
                            "Id": 101,
                            "SerialNr": 12345,
                            "ArtNr": 0,
                            "SDate": "2024-11-01T00:00:00",
                            "SValue": 38.3,
                            "EDate": "2024-11-30T00:00:00",
                            "EValue": 42.5,
                            "CValue": 4.2,
                            "CCDValue": 0.0,
                            "Active": "2020-01-01T00:00:00",
                            "MainDevice": None,
                        }
                    ],
                },
                {
                    "ServiceId": 2,
                    "TotalConsumption": 1.5,
                    "BuldingAverage": 1.8,
                    "HasApproximation": False,
                    "DeviceConsumptions": [
                        {
                            "Id": 201,
                            "SerialNr": 67890,
                            "ArtNr": 0,
                            "SDate": "2024-11-01T00:00:00",
                            "SValue": 16.5,
                            "EDate": "2024-11-30T00:00:00",
                            "EValue": 18.0,
                            "CValue": 1.5,
                            "CCDValue": 0.0,
                            "Active": "2020-01-01T00:00:00",
                            "MainDevice": None,
                        }
                    ],
                },
            ],
        },
        {
            "y": 2024,
            "m": 10,
            "at": None,  # KNMI data not yet available
            "ServiceConsumptions": [
                {
                    "ServiceId": 1,
                    "TotalConsumption": 3.8,
                    "BuldingAverage": 4.5,
                    "HasApproximation": False,
                    "DeviceConsumptions": [],
                }
            ],
        },
    ],
}

MOCK_AVG_VALUES: dict = {
    "JWT": "refreshed-jwt-token",
    "Averages": [
        {"BillingServiceId": 1, "NormalizedValue": 46.0},
        {"BillingServiceId": 2, "NormalizedValue": 19.5},
    ],
}


# ---------------------------------------------------------------------------
# Config entry fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_config_entry(hass):
    """Return a mock config entry (not yet added to hass)."""
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.data_entry_flow import FlowResultType

    return {
        CONF_USERNAME: "test@example.com",
        CONF_PASSWORD: "secret",
        CONF_UPDATE_INTERVAL: 24,
    }


# ---------------------------------------------------------------------------
# API mock factory
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_api():
    """Patch MijnIstaAPI so no real HTTP calls are made."""
    with patch(
        "custom_components.mijn_ista.config_flow.MijnIstaAPI", autospec=True
    ) as mock_cls:
        instance = mock_cls.return_value
        instance.authenticate = AsyncMock()
        instance.get_user_values = AsyncMock(return_value=MOCK_USER_VALUES)
        instance.get_month_values = AsyncMock(return_value=MOCK_MONTH_VALUES)
        instance.get_consumption_values = AsyncMock(return_value={})
        instance.get_consumption_averages = AsyncMock(return_value=MOCK_AVG_VALUES)
        yield instance
