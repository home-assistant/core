"""Tests for the iotty integration."""
from unittest.mock import MagicMock

from homeassistant.components.iotty.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iotty: MagicMock,
    oauth_impl,
) -> None:
    """Test the configuration entry loading/unloading."""

    mock_config_entry.add_to_hass(hass)
    assert mock_config_entry.data["auth_implementation"] is not None

    config_entry_oauth2_flow.async_register_implementation(hass, DOMAIN, oauth_impl)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    ## Calls both ctor and 'init' method
    assert len(mock_iotty.mock_calls) == 2

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_component(hass: HomeAssistant) -> None:
    """Testing init CloudApi proxy."""

    entry = MockConfigEntry(domain="iotty", entry_id="00:00:00:00:01")
    entry.add_to_hass(hass)

    success = await async_setup_component(hass, "iotty", {})
    await hass.async_block_till_done()

    assert success is True
