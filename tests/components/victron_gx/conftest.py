"""Common fixtures for the victron_gx tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from victron_mqtt.testing import create_mocked_hub

from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.victron_gx.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
async def init_integration(hass: HomeAssistant, mock_config_entry):
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
