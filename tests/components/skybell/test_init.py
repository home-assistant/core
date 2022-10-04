"""Test Skybell integration."""
from datetime import timedelta
from http import HTTPStatus

from homeassistant.components.skybell.const import DEFAULT_NAME, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
import homeassistant.util.dt as dt_util

from .conftest import BASE_URL, CONF_DATA, DEVICE_ID, async_init_integration

from tests.common import async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup_config_and_unload(hass: HomeAssistant, connection) -> None:
    """Test Skybell setup and unload."""
    entry = await async_init_integration(hass)
    assert entry.state == ConfigEntryState.LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.data == CONF_DATA

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_update_failed(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, connection
) -> None:
    """Test Skybell setup and failed update."""
    entry = await async_init_integration(hass)
    assert entry.state == ConfigEntryState.LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.data == CONF_DATA

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        f"{BASE_URL}devices/{DEVICE_ID}/avatar/",
        text='{"foo": "bar"}',
        status=HTTPStatus.INTERNAL_SERVER_ERROR,
    )
    next_update = dt_util.utcnow() + timedelta(seconds=30)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.front_door_button")
    assert state.state == STATE_UNAVAILABLE


async def test_async_setup_entry_invalid_auth(
    hass: HomeAssistant, auth_exception
) -> None:
    """Test throws ConfigEntryNotReady when invalid auth occurs during setup."""
    entry = await async_init_integration(hass)
    assert entry.state == ConfigEntryState.SETUP_ERROR


async def test_async_setup_entry_not_ready(hass: HomeAssistant, not_ready) -> None:
    """Test throws ConfigEntryNotReady when exception occurs during setup."""
    entry = await async_init_integration(hass)
    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_device_info(hass: HomeAssistant, connection) -> None:
    """Test device info."""
    await async_init_integration(hass)
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device({(DOMAIN, DEVICE_ID)})

    assert device.connections == {("mac", "ff:ff:ff:ff:ff:ff")}
    assert device.identifiers == {(DOMAIN, DEVICE_ID)}
    assert device.manufacturer == DEFAULT_NAME
    assert device.model == "skybell hd"
    assert device.name == "Front door"
    assert device.sw_version == "7082"
