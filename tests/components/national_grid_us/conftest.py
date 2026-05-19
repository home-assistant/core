"""Fixtures for the National Grid US integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.national_grid_us.const import (
    CONF_SELECTED_ACCOUNTS,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_USERNAME = "testuser@example.com"
MOCK_PASSWORD = "testpassword123"
MOCK_ACCOUNT_ID = "1234567890"
MOCK_ACCOUNT_ID_2 = "0987654321"
MOCK_SERVICE_POINT = "SP001"
MOCK_SERVICE_POINT_2 = "SP002"


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a mock config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_USERNAME,
        data={
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
            CONF_SELECTED_ACCOUNTS: [MOCK_ACCOUNT_ID],
        },
        unique_id="testuser_example_com",
    )
    config_entry.add_to_hass(hass)
    return config_entry


def mock_billing_account(account_id: str = MOCK_ACCOUNT_ID) -> dict:
    """Return a mock billing account."""
    return {
        "billingAccountId": account_id,
        "region": "KEDNY",
        "premiseNumber": "PREM001",
        "serviceAddress": {"serviceAddressCompressed": "123 Main St, NY"},
        "meter": {
            "nodes": [
                {
                    "servicePointNumber": MOCK_SERVICE_POINT,
                    "meterNumber": "MTR001",
                    "meterPointNumber": "MPT001",
                    "fuelType": "Electric",
                    "hasAmiSmartMeter": True,
                    "isSmartMeter": True,
                },
                {
                    "servicePointNumber": MOCK_SERVICE_POINT_2,
                    "meterNumber": "MTR002",
                    "meterPointNumber": "MPT002",
                    "fuelType": "Gas",
                    "hasAmiSmartMeter": False,
                    "isSmartMeter": False,
                },
            ],
        },
    }


def mock_usages() -> list[dict]:
    """Return mock energy usages."""
    return [
        {"usageType": "TOTAL_KWH", "usageYearMonth": 202501, "usage": 500.0},
        {"usageType": "CCF", "usageYearMonth": 202501, "usage": 30.0},
    ]


def mock_costs() -> list[dict]:
    """Return mock energy costs."""
    return [
        {"fuelType": "ELECTRIC", "month": 202501, "amount": 120.50},
        {"fuelType": "GAS", "month": 202501, "amount": 45.00},
    ]


def make_api_mock() -> AsyncMock:
    """Create a mock NationalGridClient."""
    api = AsyncMock()
    api.get_billing_account = AsyncMock(return_value=mock_billing_account())
    api.get_energy_usages = AsyncMock(return_value=mock_usages())
    api.get_energy_usage_costs = AsyncMock(return_value=mock_costs())
    return api


@pytest.fixture
def mock_national_grid_api() -> Generator[AsyncMock]:
    """Mock the NationalGridClient."""
    with patch(
        "homeassistant.components.national_grid_us.coordinator.NationalGridClient",
        return_value=make_api_mock(),
    ) as mock_client:
        yield mock_client.return_value
