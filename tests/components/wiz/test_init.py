"""Tests for wiz integration."""
import datetime
from unittest.mock import AsyncMock

from homeassistant import config_entries
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from . import (
    FAKE_MAC,
    FAKE_SOCKET,
    _mocked_wizlight,
    _patch_discovery,
    _patch_wizlight,
    async_setup_integration,
)

from tests.common import async_fire_time_changed


async def test_setup_retry(hass: HomeAssistant) -> None:
    """Test setup is retried on error."""
    bulb = _mocked_wizlight(None, None, FAKE_SOCKET)
    bulb.getMac = AsyncMock(side_effect=OSError)
    _, entry = await async_setup_integration(hass, wizlight=bulb)
    assert entry.state == config_entries.ConfigEntryState.SETUP_RETRY
    bulb.getMac = AsyncMock(return_value=FAKE_MAC)

    with _patch_discovery(), _patch_wizlight(device=bulb):
        async_fire_time_changed(hass, utcnow() + datetime.timedelta(minutes=15))
        await hass.async_block_till_done()
    assert entry.state == config_entries.ConfigEntryState.LOADED


async def test_cleanup_on_shutdown(hass: HomeAssistant) -> None:
    """Test the socket is cleaned up on shutdown."""
    bulb = _mocked_wizlight(None, None, FAKE_SOCKET)
    _, entry = await async_setup_integration(hass, wizlight=bulb)
    assert entry.state == config_entries.ConfigEntryState.LOADED
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    bulb.async_close.assert_called_once()


async def test_cleanup_on_failed_first_update(hass: HomeAssistant) -> None:
    """Test the socket is cleaned up on failed first update."""
    bulb = _mocked_wizlight(None, None, FAKE_SOCKET)
    bulb.updateState = AsyncMock(side_effect=OSError)
    _, entry = await async_setup_integration(hass, wizlight=bulb)
    assert entry.state == config_entries.ConfigEntryState.SETUP_RETRY
    bulb.async_close.assert_called_once()


async def test_wrong_device_now_has_our_ip(hass: HomeAssistant) -> None:
    """Test setup is retried when the wrong device is found."""
    bulb = _mocked_wizlight(None, None, FAKE_SOCKET)
    bulb.mac = "dddddddddddd"
    _, entry = await async_setup_integration(hass, wizlight=bulb)
    assert entry.state == config_entries.ConfigEntryState.SETUP_RETRY
