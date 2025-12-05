"""Fixtures for Lytiva integration tests."""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.lytiva.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.lytiva.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_mqtt_client() -> Generator[MagicMock, None, None]:
    """Mock paho MQTT client."""
    with patch("homeassistant.components.lytiva.mqtt_client.Client") as mock_client:
        client_instance = MagicMock()
        client_instance.connect = MagicMock(return_value=0)
        client_instance.loop_start = MagicMock(return_value=None)
        client_instance.loop_stop = MagicMock(return_value=None)
        client_instance.disconnect = MagicMock(return_value=None)
        client_instance.subscribe = MagicMock(return_value=(0, 1))
        client_instance.publish = MagicMock(return_value=MagicMock(rc=0))
        client_instance.message_callback_add = MagicMock(return_value=None)
        client_instance.username_pw_set = MagicMock(return_value=None)
        
        mock_client.return_value = client_instance
        yield client_instance


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
async def mock_lytiva_setup(
    hass: HomeAssistant, mock_mqtt_client: MagicMock
) -> MockConfigEntry:
    """Set up the Lytiva integration with mocked MQTT."""
    entry = MockConfigEntry(
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
    entry.add_to_hass(hass)
    
    with patch("homeassistant.components.lytiva.mqtt_client.Client", return_value=mock_mqtt_client):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    
    return entry
