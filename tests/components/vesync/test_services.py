"""Tests for VeSync services."""

from unittest.mock import AsyncMock

import pytest
from pyvesync import VeSync

from homeassistant.components.vesync.const import DOMAIN, SERVICE_UPDATE_DEVS
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er


@pytest.mark.usefixtures("manager")
async def test_async_new_device_discovery_no_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> None:
    """Service should raise when no config entry exists."""

    # Set up the config entry so the service is registered, then remove the
    # entry so the service has no entries to operate on.
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError, match="Entry not found"):
        await hass.services.async_call(DOMAIN, SERVICE_UPDATE_DEVS, {}, blocking=True)


@pytest.mark.usefixtures("manager")
async def test_async_new_device_discovery_entry_not_loaded(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> None:
    """Service should raise when entry exists but is not loaded."""

    # Set up the config entry so the service is registered, then unload it.
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED

    with pytest.raises(ServiceValidationError, match="Entry not loaded"):
        await hass.services.async_call(DOMAIN, SERVICE_UPDATE_DEVS, {}, blocking=True)


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
