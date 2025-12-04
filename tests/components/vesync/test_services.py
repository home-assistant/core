"""Tests for VeSync services."""

import pytest
from pyvesync import VeSync

from homeassistant.components.vesync import async_setup
from homeassistant.components.vesync.const import (
    DOMAIN,
    SERVICE_UPDATE_DEVS,
    VS_MANAGER,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError


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
    hass: HomeAssistant, config_entry: ConfigEntry, manager: VeSync, fan, humidifier
) -> None:
    """Test new device discovery."""

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    # Assert platforms loaded
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    assert not hass.data[DOMAIN][VS_MANAGER].devices

    # Mock discovery of new fan which would get added to VS_DEVICES.
    manager._dev_list["fans"].append(fan)
    await hass.services.async_call(DOMAIN, SERVICE_UPDATE_DEVS, {}, blocking=True)

    assert manager.get_devices.call_count == 1
    assert hass.data[DOMAIN][VS_MANAGER] == manager
    assert list(hass.data[DOMAIN][VS_MANAGER].devices) == [fan]

    # Mock discovery of new humidifier which would invoke discovery in all platforms.
    manager._dev_list["humidifiers"].append(humidifier)
    await hass.services.async_call(DOMAIN, SERVICE_UPDATE_DEVS, {}, blocking=True)

    assert manager.get_devices.call_count == 2
    assert hass.data[DOMAIN][VS_MANAGER] == manager
    assert list(hass.data[DOMAIN][VS_MANAGER].devices) == [fan, humidifier]
