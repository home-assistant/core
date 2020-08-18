"""Test the Smart Meter Texas module."""
import pytest
from smart_meter_texas.const import BASE_ENDPOINT, LATEST_OD_READ_ENDPOINT

from homeassistant.components.smart_meter_texas import async_setup_entry
from homeassistant.components.smart_meter_texas.const import DATA_COORDINATOR, DOMAIN
from homeassistant.config_entries import ENTRY_STATE_NOT_LOADED
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.setup import async_setup_component

from .conftest import mock_connection, setup_integration


async def test_setup_with_no_config(hass):
    """Test that no config is successful."""
    assert await async_setup_component(hass, DOMAIN, {}) is True

    # Assert no flows were started.
    assert len(hass.config_entries.flow.async_progress()) == 0

    # Assert no config is created.
    assert hass.data[DOMAIN] == {}


async def test_auth_failure(hass, config_entry, aioclient_mock):
    """Test if user's username or password is not accepted."""
    mock_connection(aioclient_mock, auth_fail=True)
    result = await async_setup_entry(hass, config_entry)

    assert result is False


async def test_api_timeout(hass, config_entry, aioclient_mock):
    """Test that a timeout results in ConfigEntryNotReady."""
    mock_connection(aioclient_mock, auth_timeout=True)
    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, config_entry)

    assert config_entry.state == ENTRY_STATE_NOT_LOADED


async def test_update_failure(hass, config_entry, aioclient_mock):
    """Test that the coordinator handles a bad response."""
    # mock_connection(aioclient_mock)
    aioclient_mock.post(
        f"{BASE_ENDPOINT}{LATEST_OD_READ_ENDPOINT}", json={},
    )
    await setup_integration(hass, config_entry, aioclient_mock)
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]
    await coordinator.async_refresh()

    assert not coordinator.last_update_success


async def test_unload_config_entry(hass, config_entry, aioclient_mock):
    """Test entry unloading."""
    await setup_integration(hass, config_entry, aioclient_mock)
    assert hass.data[DOMAIN]
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert not hass.data.get(DOMAIN)
