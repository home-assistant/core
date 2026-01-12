"""Common fixtures for the Victron Energy tests."""

from __future__ import annotations

from collections.abc import Generator
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.victronenergy.const import (
    CONF_BROKER,
    CONF_PORT,
    CONF_USERNAME,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Victron Energy GX",
        domain=DOMAIN,
        data={
            CONF_BROKER: "192.168.1.100",
            CONF_PORT: 8883,
            CONF_USERNAME: "token/homeassistant/test_device_id",
            "token": "test_secure_token_123",
            "ha_device_id": "test_device_id",
        },
        unique_id="48e7da868f12",
    )


@pytest.fixture
def mock_mqtt_client() -> Generator[MagicMock]:
    """Mock MQTT client."""
    with patch("paho.mqtt.client.Client") as mock_client:
        client = MagicMock()
        mock_client.return_value = client

        # Mock connection methods
        client.connect.return_value = 0
        client.connect_async.return_value = None  # Add this for async connection
        client.loop_start.return_value = None
        client.loop_stop.return_value = None
        client.disconnect.return_value = None
        client.subscribe.return_value = (0, 1)
        client.unsubscribe.return_value = (0, 1)
        client.publish.return_value = MagicMock(rc=0)

        # Mock callbacks
        client.on_connect = None
        client.on_message = None
        client.on_disconnect = None

        yield client


@pytest.fixture
def mock_data() -> dict:
    """Load mock MQTT data."""
    fixture_path = Path(__file__).parent / "fixtures" / "mock_data.json"
    with fixture_path.open() as f:
        return json.load(f)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.victronenergy.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: MagicMock,
) -> MockConfigEntry:
    """Set up the Victron Energy integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.victronenergy.mqtt_client.Client",
        return_value=mock_mqtt_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return ["sensor", "binary_sensor", "number", "switch"]
