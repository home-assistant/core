"""Test init for Snoo."""

from unittest.mock import AsyncMock

from python_snoo.exceptions import InvalidSnooAuth, SnooAuthException

from homeassistant.components.snoo import SnooDeviceError
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from . import async_init_integration


async def test_async_setup_entry(hass: HomeAssistant, bypass_api: AsyncMock) -> None:
    """Test a successful setup entry."""
    entry = await async_init_integration(hass)
    assert len(hass.states.async_all("sensor")) == 2
    assert entry.state is ConfigEntryState.LOADED


async def test_cannot_auth(hass: HomeAssistant, bypass_api: AsyncMock) -> None:
    """Test that we are put into retry when we fail to auth."""
    bypass_api.authorize.side_effect = SnooAuthException
    entry = await async_init_integration(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_invalid_auth_starts_reauth(
    hass: HomeAssistant, bypass_api: AsyncMock
) -> None:
    """Test that rejected credentials during setup start a reauth flow."""
    bypass_api.authorize.side_effect = InvalidSnooAuth
    entry = await async_init_integration(hass)
    assert entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == entry.entry_id


async def test_failed_devices(hass: HomeAssistant, bypass_api: AsyncMock) -> None:
    """Test that we are put into retry when we fail to get devices."""
    bypass_api.get_devices.side_effect = SnooDeviceError
    entry = await async_init_integration(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY
