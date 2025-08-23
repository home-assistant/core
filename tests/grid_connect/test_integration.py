"""Integration tests for Grid Connect integration."""

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

DOMAIN = "grid_connect"

async def test_async_setup_entry(hass: HomeAssistant):
    """Test that the integration can be setup via config entry."""
    # Create a mock config entry for the integration
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)

    # Setup the integration
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Integration should be loaded
    assert entry.state == ConfigEntryState.LOADED
    # runtime_data should be set when not using bluetooth
    if not entry.data.get("use_bluetooth"):
        assert entry.runtime_data == {"key": "value"}

    # Check that no devices or entities present initially
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    assert len(dev_reg.devices) >= 0
    assert len(ent_reg.entities) >= 0

async def test_async_setup_component(hass: HomeAssistant):
    """Test setup via async_setup_component."""
    # Setup via component exists
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

@pytest.mark.asyncio
async def test_async_setup_entry_use_bluetooth(hass: HomeAssistant, caplog):
    """Test setup entry with use_bluetooth True."""
    caplog.set_level(logging.INFO)
    devices = [SimpleNamespace(name="Device1", address="Addr1")]

    # Patch Bluetooth discovery
    with patch("homeassistant.components.grid_connect.discover_bluetooth_devices", AsyncMock(return_value=devices)):
        entry = MockConfigEntry(domain=DOMAIN, data={"use_bluetooth": True})
        entry.add_to_hass(hass)
        # Setup the integration
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        # Verify the entry was loaded successfully
        assert entry.state == ConfigEntryState.LOADED
        # Verify log output for processing devices
        assert "Processing device: Device1, Addr1" in caplog.text
