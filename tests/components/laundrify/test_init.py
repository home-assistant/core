"""Test the laundrify init file."""

from laundrify_aio import exceptions

from homeassistant.components.laundrify.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import create_entry


async def test_setup_entry_api_unauthorized(
    hass: HomeAssistant, laundrify_validate_token
) -> None:
    """Test that ConfigEntryAuthFailed is thrown when authentication fails."""
    laundrify_validate_token.side_effect = exceptions.UnauthorizedException
    config_entry = create_entry(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state == ConfigEntryState.SETUP_ERROR
    assert not hass.data.get(DOMAIN)


async def test_setup_entry_api_cannot_connect(
    hass: HomeAssistant, laundrify_validate_token
) -> None:
    """Test that ApiConnectionException is thrown when connection fails."""
    laundrify_validate_token.side_effect = exceptions.ApiConnectionException
    config_entry = create_entry(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state == ConfigEntryState.SETUP_RETRY
    assert not hass.data.get(DOMAIN)


async def test_setup_entry_successful(hass: HomeAssistant) -> None:
    """Test entry can be setup successfully."""
    config_entry = create_entry(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state == ConfigEntryState.LOADED


async def test_setup_entry_unload(hass: HomeAssistant) -> None:
    """Test unloading the laundrify entry."""
    config_entry = create_entry(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.config_entries.async_unload(config_entry.entry_id)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state == ConfigEntryState.NOT_LOADED
