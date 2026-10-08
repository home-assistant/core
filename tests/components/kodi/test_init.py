"""Test the Kodi integration init."""

from unittest.mock import patch

from pykodi import InvalidAuthError

from homeassistant.components.kodi.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import init_integration
from .util import MockConnection


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test successful unload of entry."""
    with patch(
        "homeassistant.components.kodi.media_player.async_setup_entry",
        return_value=True,
    ):
        entry = await init_integration(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_setup_invalid_auth(hass: HomeAssistant) -> None:
    """Test setup fails when login is rejected."""
    with patch.object(
        MockConnection, "connect", side_effect=InvalidAuthError("Unauthorized")
    ):
        entry = await init_integration(hass)

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.reason == "Login to 1.1.1.1 failed"
