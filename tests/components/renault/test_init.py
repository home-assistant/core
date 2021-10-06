"""Tests for Renault setup process."""
from unittest.mock import patch

import aiohttp
from renault_api.gigya.exceptions import InvalidCredentialsException

from homeassistant.components.renault.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import get_mock_config_entry, setup_renault_integration_simple


async def test_setup_unload_entry(hass: HomeAssistant):
    """Test entry setup and unload."""
    with patch("homeassistant.components.renault.PLATFORMS", []):
        config_entry = await setup_renault_integration_simple(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.entry_id in hass.data[DOMAIN]

    # Unload the entry and verify that the data has been removed
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert config_entry.entry_id not in hass.data[DOMAIN]


async def test_setup_entry_bad_password(hass: HomeAssistant):
    """Test entry setup and unload."""
    # Create a mock entry so we don't have to go through config flow
    config_entry = get_mock_config_entry()
    config_entry.add_to_hass(hass)

    with patch(
        "renault_api.renault_session.RenaultSession.login",
        side_effect=InvalidCredentialsException(403042, "invalid loginID or password"),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert not hass.data.get(DOMAIN)


async def test_setup_entry_exception(hass: HomeAssistant):
    """Test ConfigEntryNotReady when API raises an exception during entry setup."""
    config_entry = get_mock_config_entry()
    config_entry.add_to_hass(hass)

    # In this case we are testing the condition where async_setup_entry raises
    # ConfigEntryNotReady.
    with patch(
        "renault_api.renault_session.RenaultSession.login",
        side_effect=aiohttp.ClientConnectionError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.data.get(DOMAIN)
