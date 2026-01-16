"""Tests for VeSync services."""

from unittest.mock import AsyncMock

import pytest
from pyvesync import VeSync

from homeassistant.components.vesync import async_setup
from homeassistant.components.vesync.const import DOMAIN, SERVICE_UPDATE_DEVS
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er


async def test_async_new_device_discovery_no_entry(
    hass: HomeAssistant,
) -> None:
    """Service should raise when no config entry exists."""

    # Ensure the integration is set up so the service is registered
    assert await async_setup(hass, {})

    # No entries for the domain, service should raise
    with pytest.raises(ServiceValidationError, match="Entry not found"):
        await hass.services.async_call("vesync", SERVICE_UPDATE_DEVS, {}, blocking=True)


async def test_async_new_device_discovery_entry_not_loaded(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Service should raise when entry exists but is not loaded."""

    # Add a config entry but do not set it up (state is not LOADED)
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    # Ensure the integration is set up so the service is registered
    assert await async_setup(hass, {})

    with pytest.raises(ServiceValidationError, match="Entry not loaded"):
        await hass.services.async_call("vesync", SERVICE_UPDATE_DEVS, {}, blocking=True)


async def test_async_new_device_discovery(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    manager: VeSync,
    fan,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test new device discovery."""

    # Entry should not be set up yet; we'll install a fan before setup
    assert config_entry.state is ConfigEntryState.NOT_LOADED

    # Set up the config entry (no devices initially)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    # Simulate the manager discovering a new fan when get_devices is called
    manager.get_devices = AsyncMock(
        side_effect=lambda: manager._dev_list["fans"].append(fan)
    )

    # Call the service that should trigger discovery and platform setup
    await hass.services.async_call(DOMAIN, SERVICE_UPDATE_DEVS, {}, blocking=True)
    await hass.async_block_till_done()

    assert manager.get_devices.call_count == 1

    # Verify an entity for the new fan was created in Home Assistant
    fan_entry = next(
        (
            e
            for e in entity_registry.entities.values()
            if e.unique_id == fan.cid and e.domain == "fan"
        ),
        None,
    )
    assert fan_entry is not None
