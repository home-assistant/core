"""Tests for the KEF integration setup."""

import aiohttp

from homeassistant.components.kef.coordinator import KefCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import FakeKefConnector

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    mock_connector: FakeKefConnector,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting up a KEF config entry."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert isinstance(mock_config_entry.runtime_data, KefCoordinator)
    assert mock_config_entry.runtime_data.connector is mock_connector
    assert hass.states.get("media_player.test_kef_speaker") is not None


async def test_unload_entry(
    hass: HomeAssistant,
    mock_connector: FakeKefConnector,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading a KEF config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_not_ready(
    hass: HomeAssistant,
    mock_connector: FakeKefConnector,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries when the speaker cannot be reached."""
    mock_connector.mac_address_error = aiohttp.ClientError()
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
