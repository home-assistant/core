"""Test init for Snoo."""

from unittest.mock import AsyncMock, patch

from python_snoo.exceptions import SnooAuthException

from homeassistant.components.snoo import SnooDeviceError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import async_init_integration


async def test_async_setup_entry(hass: HomeAssistant, bypass_api: AsyncMock) -> None:
    """Test a successful setup entry."""
    entry = await async_init_integration(hass)
    assert len(hass.states.async_all("sensor")) == 2
    assert entry.state == ConfigEntryState.LOADED


async def test_cannot_auth(hass: HomeAssistant) -> None:
    """Test that we are put into retry when we fail to auth."""
    with patch(
        "homeassistant.components.snoo.Snoo.authorize", side_effect=SnooAuthException
    ):
        entry = await async_init_integration(hass)
        assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_failed_devices(hass: HomeAssistant) -> None:
    """Test that we are put into rretry when we fail to get devices."""
    with (
        patch("homeassistant.components.snoo.Snoo.authorize"),
        patch(
            "homeassistant.components.snoo.Snoo.get_devices",
            side_effect=SnooDeviceError,
        ),
    ):
        entry = await async_init_integration(hass)
        assert entry.state == ConfigEntryState.SETUP_RETRY
