"""Test Efergy integration."""
from pyefergy import exceptions

from homeassistant.components.efergy.const import DEFAULT_NAME, DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import _patch_efergy_status, create_entry, init_integration, setup_platform

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Test unload."""
    entry = await init_integration(hass, aioclient_mock)
    assert entry.state == ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_async_setup_entry_not_ready(hass: HomeAssistant) -> None:
    """Test that it throws ConfigEntryNotReady when exception occurs during setup."""
    entry = create_entry(hass)
    with _patch_efergy_status() as efergymock:
        efergymock.side_effect = (exceptions.ConnectError, exceptions.DataError)
        await hass.config_entries.async_setup(entry.entry_id)
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1
        assert entry.state == ConfigEntryState.SETUP_RETRY
        assert not hass.data.get(DOMAIN)


async def test_async_setup_entry_auth_failed(hass: HomeAssistant) -> None:
    """Test that it throws ConfigEntryAuthFailed when authentication fails."""
    entry = create_entry(hass)
    with _patch_efergy_status() as efergymock:
        efergymock.side_effect = exceptions.InvalidAuth
        await hass.config_entries.async_setup(entry.entry_id)
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1
        assert entry.state == ConfigEntryState.SETUP_ERROR
        assert not hass.data.get(DOMAIN)


async def test_device_info(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test device info."""
    entry = await setup_platform(hass, aioclient_mock, SENSOR_DOMAIN)
    device_registry = dr.async_get(hass)

    device = device_registry.async_get_device({(DOMAIN, entry.entry_id)})

    assert device.configuration_url == "https://engage.efergy.com/user/login"
    assert device.connections == {("mac", "ff:ff:ff:ff:ff:ff")}
    assert device.identifiers == {(DOMAIN, entry.entry_id)}
    assert device.manufacturer == DEFAULT_NAME
    assert device.model == "EEEHub"
    assert device.name == DEFAULT_NAME
    assert device.sw_version == "2.3.7"
