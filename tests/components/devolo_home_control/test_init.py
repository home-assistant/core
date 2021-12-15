"""Tests for the devolo Home Control integration."""
from unittest.mock import patch

from devolo_home_control_api.exceptions.gateway import GatewayOfflineError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.components.devolo_home_control import configure_integration


async def test_setup_entry(hass: HomeAssistant, mock_zeroconf):
    """Test setup entry."""
    entry = configure_integration(hass)
    with patch("homeassistant.components.devolo_home_control.HomeControl"):
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.LOADED


@pytest.mark.credentials_invalid
async def test_setup_entry_credentials_invalid(hass: HomeAssistant):
    """Test setup entry fails if credentials are invalid."""
    entry = configure_integration(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.maintenance
async def test_setup_entry_maintenance(hass: HomeAssistant):
    """Test setup entry fails if mydevolo is in maintenance mode."""
    entry = configure_integration(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_gateway_offline(hass: HomeAssistant, mock_zeroconf):
    """Test setup entry fails on gateway offline."""
    entry = configure_integration(hass)
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=GatewayOfflineError,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(hass: HomeAssistant):
    """Test unload entry."""
    entry = configure_integration(hass)
    with patch("homeassistant.components.devolo_home_control.HomeControl"):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await hass.config_entries.async_unload(entry.entry_id)
        assert entry.state is ConfigEntryState.NOT_LOADED
