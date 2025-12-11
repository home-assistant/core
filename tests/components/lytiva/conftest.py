"""Fixtures for Lytiva integration tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.lytiva.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_mqtt_client():
    """Create a mock MQTT client instance."""
    client = MagicMock()
    client.connect = MagicMock(return_value=0)
    client.loop_start = MagicMock(return_value=None)
    client.loop_stop = MagicMock(return_value=None)
    client.disconnect = MagicMock(return_value=None)
    client.subscribe = MagicMock(return_value=(0, 1))
    client.publish = MagicMock(return_value=MagicMock(rc=0))
    client.message_callback_add = MagicMock(return_value=None)
    client.username_pw_set = MagicMock(return_value=None)
    client.will_set = MagicMock(return_value=None)
    
    # Store callbacks for testing
    client.on_connect = None
    client.on_message = None
    
    return client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Lytiva (192.168.1.100)",
        data={
            "broker": "192.168.1.100",
            CONF_PORT: 1883,
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_pass",
        },
        options={
            "discovery_prefix": "homeassistant",
        },
        unique_id="lytiva_192.168.1.100",
    )


@pytest.fixture
async def setup_integration(hass: HomeAssistant, mock_mqtt_client: MagicMock):
    """Set up the Lytiva integration with mocked MQTT."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Lytiva Test",
        data={
            "broker": "192.168.1.100",
            CONF_PORT: 1883,
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.lytiva.mqtt_client.Client",
        return_value=mock_mqtt_client,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Trigger on_connect to set up subscriptions
        if mock_mqtt_client.on_connect:
            mock_mqtt_client.on_connect(mock_mqtt_client, None, {}, 0)
            await hass.async_block_till_done()

    return entry
