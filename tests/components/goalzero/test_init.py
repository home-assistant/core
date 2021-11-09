"""Test Goal Zero integration."""
from datetime import timedelta
from unittest.mock import patch

from goalzero import exceptions

from homeassistant.components.goalzero.const import (
    DATA_KEY_COORDINATOR,
    DEFAULT_NAME,
    DOMAIN,
    MANUFACTURER,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
import homeassistant.util.dt as dt_util

from . import (
    CONF_DATA,
    _create_mocked_yeti,
    _patch_init_yeti,
    async_init_integration,
    create_entry,
)

from tests.common import async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup_config_and_unload(hass: HomeAssistant):
    """Test Goal Zero setup and unload."""
    entry = create_entry(hass)
    with _patch_init_yeti(await _create_mocked_yeti()):
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.data == CONF_DATA

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_async_setup_entry_not_ready(hass: HomeAssistant):
    """Test that it throws ConfigEntryNotReady when exception occurs during setup."""
    entry = create_entry(hass)
    with patch(
        "homeassistant.components.goalzero.Yeti.init_connect",
        side_effect=exceptions.ConnectError,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_update_failed(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test data update failure."""
    entry = await async_init_integration(hass, aioclient_mock)
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_KEY_COORDINATOR
    ]
    with patch(
        "homeassistant.components.goalzero.Yeti.get_state",
        side_effect=exceptions.ConnectError,
    ) as updater:
        next_update = dt_util.utcnow() + timedelta(seconds=30)
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()
        updater.assert_called_once()
        assert not coordinator.last_update_success


async def test_device_info(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker):
    """Test device info."""
    entry = await async_init_integration(hass, aioclient_mock)
    device_registry = await dr.async_get_registry(hass)

    device = device_registry.async_get_device({(DOMAIN, entry.entry_id)})

    assert device.connections == {("mac", "12:34:56:78:90:12")}
    assert device.identifiers == {(DOMAIN, entry.entry_id)}
    assert device.manufacturer == MANUFACTURER
    assert device.model == "Yeti 1400"
    assert device.name == DEFAULT_NAME
    assert device.sw_version == "1.5.7"
