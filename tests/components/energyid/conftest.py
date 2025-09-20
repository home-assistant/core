"""Shared test configuration for EnergyID tests."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.energyid.const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_PROVISIONING_KEY,
    CONF_PROVISIONING_SECRET,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_energyid_config_entry(hass: HomeAssistant):
    """Create a mock EnergyID config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test EnergyID Site",
        data={
            CONF_PROVISIONING_KEY: "test_provisioning_key",
            CONF_PROVISIONING_SECRET: "test_provisioning_secret",
            CONF_DEVICE_ID: "test_device_id",
            CONF_DEVICE_NAME: "Test Device",
        },
        unique_id="test_site_12345",
        entry_id="test_entry_id",
        state=ConfigEntryState.NOT_LOADED,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_webhook_client():
    """Create a mock WebhookClient for testing."""
    client = MagicMock()

    # Default successful authentication
    client.authenticate = MagicMock(return_value=True)
    client.device_name = "Test Device"
    client.recordNumber = "test_site_12345"
    client.recordName = "Test EnergyID Site"
    client.webhook_policy = {"uploadInterval": 60}

    # Sensor management
    client.get_or_create_sensor = MagicMock()
    client.start_auto_sync = MagicMock()
    client.close = MagicMock()

    return client


@pytest.fixture
def mock_unclaimed_webhook_client():
    """Create a mock WebhookClient that needs claiming."""
    client = MagicMock()

    # Unclaimed authentication
    client.authenticate = MagicMock(return_value=False)
    client.get_claim_info = MagicMock(
        return_value={
            "claim_url": "https://app.energyid.eu/claim/test",
            "claim_code": "ABC123",
            "valid_until": "2024-01-01T00:00:00Z",
        }
    )
    client.device_name = "Test Device"

    return client
