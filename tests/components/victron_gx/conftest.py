"""Common fixtures for the victron_gx tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from victron_mqtt import Hub as VictronVenusHub
from victron_mqtt.testing import create_mocked_hub

from homeassistant.components.victron_gx.const import (
    CONF_INSTALLATION_ID,
    CONF_MODEL,
    CONF_SERIAL,
    DOMAIN,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.victron_gx.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="123",
        data={
            CONF_HOST: "venus.local",
            CONF_PORT: 1883,
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_pass",
            CONF_SSL: False,
            CONF_INSTALLATION_ID: "123",
            CONF_MODEL: "Venus GX",
            CONF_SERIAL: "HQ12345678",
        },
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> tuple[VictronVenusHub, MockConfigEntry]:
    """Set up the Victron GX MQTT integration for testing."""
    mock_config_entry.add_to_hass(hass)

    victron_hub = await create_mocked_hub()

    with patch(
        "homeassistant.components.victron_gx.hub.VictronVenusHub"
    ) as mock_hub_class:
        mock_hub_class.return_value = victron_hub

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return victron_hub, mock_config_entry
