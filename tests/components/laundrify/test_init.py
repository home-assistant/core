"""Test the laundrify init file."""

from laundrify_aio import exceptions

from homeassistant.components.laundrify.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry_api_unauthorized(
    hass: HomeAssistant,
    laundrify_api_mock,
    laundrify_config_entry: MockConfigEntry,
) -> None:
    """Test that ConfigEntryAuthFailed is thrown when authentication fails."""
    laundrify_api_mock.validate_token.side_effect = exceptions.UnauthorizedException
    await hass.config_entries.async_reload(laundrify_config_entry.entry_id)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert laundrify_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert not hass.data.get(DOMAIN)


async def test_setup_entry_api_cannot_connect(
    hass: HomeAssistant,
    laundrify_api_mock,
    laundrify_config_entry: MockConfigEntry,
) -> None:
    """Test that ApiConnectionException is thrown when connection fails."""
    laundrify_api_mock.validate_token.side_effect = exceptions.ApiConnectionException
    await hass.config_entries.async_reload(laundrify_config_entry.entry_id)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert laundrify_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.data.get(DOMAIN)


async def test_setup_entry_successful(
    hass: HomeAssistant, laundrify_config_entry: MockConfigEntry
) -> None:
    """Test entry can be setup successfully."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert laundrify_config_entry.state is ConfigEntryState.LOADED


async def test_setup_entry_unload(
    hass: HomeAssistant, laundrify_config_entry: MockConfigEntry
) -> None:
    """Test unloading the laundrify entry."""
    await hass.config_entries.async_unload(laundrify_config_entry.entry_id)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert laundrify_config_entry.state is ConfigEntryState.NOT_LOADED
