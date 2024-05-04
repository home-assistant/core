"""Test Radarr integration."""

import pytest

from homeassistant.components.radarr.const import DEFAULT_NAME, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import create_entry, mock_connection_invalid_auth, setup_integration

from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.freeze_time("2021-12-03 00:00:00+00:00")
async def test_setup(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Test unload."""
    entry = await setup_integration(hass, aioclient_mock)
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_async_setup_entry_not_ready(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that it throws ConfigEntryNotReady when exception occurs during setup."""
    entry = await setup_integration(hass, aioclient_mock, connection_error=True)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.data.get(DOMAIN)


async def test_async_setup_entry_auth_failed(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that it throws ConfigEntryAuthFailed when authentication fails."""
    entry = create_entry(hass)
    mock_connection_invalid_auth(aioclient_mock)
    await hass.config_entries.async_setup(entry.entry_id)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert not hass.data.get(DOMAIN)


@pytest.mark.freeze_time("2021-12-03 00:00:00+00:00")
async def test_device_info(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test device info."""
    entry = await setup_integration(hass, aioclient_mock)
    device_registry = dr.async_get(hass)
    await hass.async_block_till_done()
    device = device_registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})

    assert device.configuration_url == "http://192.168.1.189:7887/test"
    assert device.identifiers == {(DOMAIN, entry.entry_id)}
    assert device.manufacturer == DEFAULT_NAME
    assert device.name == "Mock Title"
    assert device.sw_version == "10.0.0.34882"
