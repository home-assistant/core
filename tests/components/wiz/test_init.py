"""Tests for wiz integration."""
import datetime
from unittest.mock import AsyncMock

from homeassistant import config_entries
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
