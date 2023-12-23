"""Test the Tessie init."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .common import ERROR_AUTH, ERROR_CONNECTION, ERROR_UNKNOWN, setup_platform


async def test_load_unload(hass: HomeAssistant) -> None:
    """Test load and unload."""

    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_auth_failure(hass: HomeAssistant) -> None:
    """Test init with an authentication error."""

    entry = await setup_platform(hass, side_effect=ERROR_AUTH)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_unknown_failure(hass: HomeAssistant) -> None:
    """Test init with an client response error."""

    entry = await setup_platform(hass, side_effect=ERROR_UNKNOWN)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_connection_failure(hass: HomeAssistant) -> None:
    """Test init with a network connection error."""

    entry = await setup_platform(hass, side_effect=ERROR_CONNECTION)
    assert entry.state is ConfigEntryState.SETUP_RETRY
