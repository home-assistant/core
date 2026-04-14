"""Configuration for EffortlessHome tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.effortlesshome.const import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "email": "test@example.com",
            "firebase_uid": "test_uid",
            "id_token": "test_id_token",
            "refresh_token": "test_refresh_token",
            "customer_id": "12345",
            "system_id": "67890",
        },
        unique_id="12345_67890",
        version=2,
    )


@pytest.fixture
def parsed_customer_data() -> dict[str, object]:
    """Return parsed customer/system payload from API."""
    return {
        "fullname": "Test User",
        "phonenumber": "123-456-7890",
        "emailaddress": "test@example.com",
        "ha_token": "ha_test_token",
        "ha_url": "http://localhost:8123",
        "ai_key": "test_ai_key",
        "ai_model": "test_model",
        "influx_url": "http://influx:8086",
        "influx_token": "test_influx_token",
        "influx_bucket": "test_bucket",
        "influx_org": "test_org",
        "DaysHistoryToKeep": 30,
        "LowTemperatureWarning": 60,
        "HighTemperatureWarning": 80,
        "LowHumidityWarning": 20,
        "HighHumidityWarning": 80,
        "address_json": '{"street": "123 Main St"}',
        "systemphotolurl": "http://example.com/photo.jpg",
        "testmode": False,
        "additional_contacts_json": "[]",
        "instructions_json": "[]",
        "name": "Basic Plan",
    }


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry for config flow tests."""
    with patch(
        "homeassistant.components.effortlesshome.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup
