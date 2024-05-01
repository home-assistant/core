"""Test Goal Zero integration."""

from datetime import timedelta
from unittest.mock import patch

from goalzero import exceptions

from homeassistant.components.goalzero.const import DEFAULT_NAME, DOMAIN, MANUFACTURER
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
import homeassistant.util.dt as dt_util

from . import CONF_DATA, async_init_integration, create_entry, create_mocked_yeti

from tests.common import async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup_config_and_unload(hass: HomeAssistant) -> None:
    """Test Goal Zero setup and unload."""
    entry = create_entry(hass)
    mocked_yeti = await create_mocked_yeti()
    with patch("homeassistant.components.goalzero.Yeti", return_value=mocked_yeti):
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.data == CONF_DATA

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_setup_config_entry_incorrectly_formatted_mac(
    hass: HomeAssistant,
) -> None:
    """Test the mac address formatting is corrected."""
    entry = create_entry(hass)
    hass.config_entries.async_update_entry(entry, unique_id="AABBCCDDEEFF")
    mocked_yeti = await create_mocked_yeti()
    with patch("homeassistant.components.goalzero.Yeti", return_value=mocked_yeti):
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.data == CONF_DATA

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.unique_id == "aa:bb:cc:dd:ee:ff"


async def test_async_setup_entry_not_ready(hass: HomeAssistant) -> None:
    """Test that it throws ConfigEntryNotReady when exception occurs during setup."""
    entry = create_entry(hass)
    with patch(
        "homeassistant.components.goalzero.Yeti.init_connect",
        side_effect=exceptions.ConnectError,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_update_failed(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test data update failure."""
    await async_init_integration(hass, aioclient_mock)
    assert hass.states.get(f"switch.{DEFAULT_NAME}_ac_port_status").state == STATE_ON
    with patch(
        "homeassistant.components.goalzero.Yeti.get_state",
        side_effect=exceptions.ConnectError,
    ) as updater:
        next_update = dt_util.utcnow() + timedelta(seconds=30)
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()
        updater.assert_called_once()
        state = hass.states.get(f"switch.{DEFAULT_NAME}_ac_port_status")
        assert state.state == STATE_UNAVAILABLE


async def test_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test device info."""
    entry = await async_init_integration(hass, aioclient_mock)

    device = device_registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})

    assert device.connections == {("mac", "12:34:56:78:90:12")}
    assert device.identifiers == {(DOMAIN, entry.entry_id)}
    assert device.manufacturer == MANUFACTURER
    assert device.model == "Yeti 1400"
    assert device.name == DEFAULT_NAME
    assert device.sw_version == "1.5.7"
