"""Test the Smart Meter Texas module."""

from unittest.mock import patch

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.smart_meter_texas.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import TEST_ENTITY_ID, setup_integration

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup_with_no_config(hass: HomeAssistant) -> None:
    """Test that no config is successful."""
    assert await async_setup_component(hass, DOMAIN, {}) is True
    await hass.async_block_till_done()

    # Assert no flows were started.
    assert len(hass.config_entries.flow.async_progress()) == 0


async def test_auth_failure(
    hass: HomeAssistant, config_entry, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test if user's username or password is not accepted."""
    await setup_integration(hass, config_entry, aioclient_mock, auth_fail=True)

    assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_api_timeout(
    hass: HomeAssistant, config_entry, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that a timeout results in ConfigEntryNotReady."""
    await setup_integration(hass, config_entry, aioclient_mock, auth_timeout=True)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_update_failure(
    hass: HomeAssistant, config_entry, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that the coordinator handles a bad response."""
    await setup_integration(hass, config_entry, aioclient_mock, bad_reading=True)
    await async_setup_component(hass, HA_DOMAIN, {})
    await hass.async_block_till_done()
    with patch("smart_meter_texas.Meter.read_meter") as updater:
        await hass.services.async_call(
            HA_DOMAIN,
            SERVICE_UPDATE_ENTITY,
            {ATTR_ENTITY_ID: TEST_ENTITY_ID},
            blocking=True,
        )
        await hass.async_block_till_done()
        updater.assert_called_once()


async def test_unload_config_entry(
    hass: HomeAssistant, config_entry, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test entry unloading."""
    await setup_integration(hass, config_entry, aioclient_mock)

    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 1
    assert config_entries[0] is config_entry
    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
