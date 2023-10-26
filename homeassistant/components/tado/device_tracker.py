"""Support for Tado Smart device trackers."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Tado device scannery entity."""
    _LOGGER.debug("Setting up Tado device scanner entity")
    tado_device = hass.data[DOMAIN][entry.entry_id]
    tracked: set = set()

    @callback
    async def async_update_devices() -> None:
        """Update the values of the devices."""
        await async_add_tracked_entities(hass, tado_device, async_add_entities, tracked)

    await async_update_devices()


@callback
async def async_add_tracked_entities(
    hass: HomeAssistant,
    tado_device: Any,
    async_add_entities: AddEntitiesCallback,
    tracked: set[str],
) -> None:
    """Add new tracker entities from Tado."""
    new_tracked = []
    _LOGGER.debug("Fetching Tado devices from API")
    known_devices = await hass.async_add_executor_job(tado_device["data"].get_me)

    for device in known_devices["mobileDevices"]:
        if device["id"] in tracked:
            continue
        if device.get("location") and device["location"]["atHome"]:
            _LOGGER.debug("Adding Tado device %s", device["name"])
            new_tracked.append(
                TadoDeviceTrackerEntity(str(device["id"]), device["name"])
            )
            tracked.add(device["id"])

    _LOGGER.debug(
        "Tado presence query successful, %d device(s) at home",
        len(new_tracked),
    )
    async_add_entities(new_tracked)


class TadoDeviceTrackerEntity(ScannerEntity):
    """A Tado Device Tracker entity."""

    def __init__(self, device_id, device_name) -> None:
        """Initialize a Tado Device Tracker entity."""
        super().__init__()
        self.device_id = device_id
        self.device_name = device_name

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self.device_name

    @property
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        return self.device_id

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected and home."""
        return True

    @property
    def source_type(self) -> SourceType:
        """Return the source type."""
        return SourceType.GPS
