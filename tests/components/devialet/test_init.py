"""Test the Devialet init."""

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN, MediaPlayerState
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import NAME, setup_integration

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_load_unload_config_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the Devialet configuration entry loading and unloading."""
    entry = await setup_integration(hass, aioclient_mock)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.unique_id is not None

    state = hass.states.get(f"{MP_DOMAIN}.{NAME.lower()}")
    assert state.state == MediaPlayerState.PLAYING

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_load_unload_config_entry_when_device_unavailable(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the Devialet configuration entry loading and unloading when the device is unavailable."""
    entry = await setup_integration(hass, aioclient_mock, state="unavailable")

    assert entry.state is ConfigEntryState.LOADED
    assert entry.unique_id is not None

    state = hass.states.get(f"{MP_DOMAIN}.{NAME.lower()}")
    assert state.state == "unavailable"

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
