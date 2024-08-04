"""Tests for wiz integration."""

import datetime
from unittest.mock import AsyncMock, patch

from homeassistant.components.wiz.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_FRIENDLY_NAME, CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from . import (
    FAKE_IP,
    FAKE_MAC,
    FAKE_SOCKET,
    _mocked_wizlight,
    _patch_discovery,
    _patch_wizlight,
    async_setup_integration,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_setup_retry(hass: HomeAssistant) -> None:
    """Test setup is retried on error."""
    bulb = _mocked_wizlight(None, None, FAKE_SOCKET)
    bulb.getMac = AsyncMock(side_effect=OSError)
    _, entry = await async_setup_integration(hass, wizlight=bulb)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    bulb.getMac = AsyncMock(return_value=FAKE_MAC)

    with _patch_discovery(), _patch_wizlight(device=bulb):
        await hass.async_block_till_done(wait_background_tasks=True)
        async_fire_time_changed(hass, utcnow() + datetime.timedelta(minutes=15))
        await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.LOADED


async def test_cleanup_on_shutdown(hass: HomeAssistant) -> None:
    """Test the socket is cleaned up on shutdown."""
    bulb = _mocked_wizlight(None, None, FAKE_SOCKET)
    _, entry = await async_setup_integration(hass, wizlight=bulb)
    assert entry.state is ConfigEntryState.LOADED
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done(wait_background_tasks=True)
    bulb.async_close.assert_called_once()


async def test_cleanup_on_failed_first_update(hass: HomeAssistant) -> None:
    """Test the socket is cleaned up on failed first update."""
    bulb = _mocked_wizlight(None, None, FAKE_SOCKET)
    bulb.updateState = AsyncMock(side_effect=OSError)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FAKE_MAC,
        data={CONF_HOST: FAKE_IP},
    )
    entry.add_to_hass(hass)
    with (
        patch("homeassistant.components.wiz.discovery.find_wizlights", return_value=[]),
        _patch_wizlight(device=bulb),
    ):
        await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    bulb.async_close.assert_called_once()


async def test_wrong_device_now_has_our_ip(hass: HomeAssistant) -> None:
    """Test setup is retried when the wrong device is found."""
    bulb = _mocked_wizlight(None, None, FAKE_SOCKET)
    bulb.mac = "dddddddddddd"
    _, entry = await async_setup_integration(hass, wizlight=bulb)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_reload_on_title_change(hass: HomeAssistant) -> None:
    """Test the integration gets reloaded when the title is updated."""
    bulb = _mocked_wizlight(None, None, FAKE_SOCKET)
    _, entry = await async_setup_integration(hass, wizlight=bulb)
    assert entry.state is ConfigEntryState.LOADED
    await hass.async_block_till_done(wait_background_tasks=True)

    with _patch_discovery(), _patch_wizlight(device=bulb):
        hass.config_entries.async_update_entry(entry, title="Shop Switch")
        assert entry.title == "Shop Switch"
        await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        hass.states.get("switch.mock_title").attributes[ATTR_FRIENDLY_NAME]
        == "Shop Switch"
    )
