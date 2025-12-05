"""Shared test configuration for EnergyID tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.energyid.const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_PROVISIONING_KEY,
    CONF_PROVISIONING_SECRET,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a mock config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PROVISIONING_KEY: "test-key",
            CONF_PROVISIONING_SECRET: "test-secret",
            CONF_DEVICE_ID: "test-device",
            CONF_DEVICE_NAME: "Test Device",
        },
        entry_id="test-entry-id-123",
        title="Test EnergyID Site",
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_webhook_client() -> Generator[MagicMock]:
    """Mock the WebhookClient."""
    with patch(
        "homeassistant.components.energyid.WebhookClient", autospec=True
    ) as mock_client_class:
        client = mock_client_class.return_value
        client.authenticate = AsyncMock(return_value=True)
        client.webhook_policy = {"uploadInterval": 60}
        client.device_name = "Test Device"
        client.synchronize_sensors = AsyncMock()

        # Create a mock sensor that will be returned by get_or_create_sensor
        mock_sensor = MagicMock()
        mock_sensor.update = MagicMock()

        # Configure get_or_create_sensor to always return the same mock sensor
        client.get_or_create_sensor = MagicMock(return_value=mock_sensor)

        yield client
