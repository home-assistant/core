"""Support for scanning a network with nmap."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NmapDevice, NmapDeviceScanner, short_hostname, signal_device_update
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up device tracker for Nmap Tracker component."""
    nmap_tracker = hass.data[DOMAIN][entry.entry_id]

    @callback
    def device_new(mac_address):
        """Signal a new device."""
        async_add_entities([NmapTrackerEntity(nmap_tracker, mac_address, True)])

    @callback
    def device_missing(mac_address):
        """Signal a missing device."""
        async_add_entities([NmapTrackerEntity(nmap_tracker, mac_address, False)])

    entry.async_on_unload(
        async_dispatcher_connect(hass, nmap_tracker.signal_device_new, device_new)
    )
    entry.async_on_unload(
        async_dispatcher_connect(
            hass, nmap_tracker.signal_device_missing, device_missing
        )
    )


class NmapTrackerEntity(ScannerEntity):
    """An Nmap Tracker entity."""

    _attr_should_poll = False

    def __init__(
        self, nmap_tracker: NmapDeviceScanner, mac_address: str, active: bool
    ) -> None:
        """Initialize an nmap tracker entity."""
        self._mac_address = mac_address
        self._nmap_tracker = nmap_tracker
        self._tracked = self._nmap_tracker.devices.tracked
        self._active = active

    @property
    def _device(self) -> NmapDevice:
        """Get latest device state."""
        return self._tracked[self._mac_address]

    @property
    def is_connected(self) -> bool:
        """Return device status."""
        return self._active

    @property
    def name(self) -> str:
        """Return device name."""
        return self._device.name

    @property
    def unique_id(self) -> str:
        """Return device unique id."""
        return self._mac_address

    @property
    def ip_address(self) -> str:
        """Return the primary ip address of the device."""
        return self._device.ipv4

    @property
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        return self._mac_address

    @property
    def hostname(self) -> str | None:
        """Return hostname of the device."""
        if not self._device.hostname:
            return None
        return short_hostname(self._device.hostname)

    @property
    def source_type(self) -> SourceType:
        """Return tracker source type."""
        return SourceType.ROUTER

    @property
    def icon(self) -> str:
        """Return device icon."""
        return "mdi:lan-connect" if self._active else "mdi:lan-disconnect"

    @callback
    def async_process_update(self, online: bool) -> None:
        """Update device."""
        self._active = online

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the attributes."""
        return {
            "last_time_reachable": self._device.last_update.isoformat(
                timespec="seconds"
            ),
            "reason": self._device.reason,
        }

    @callback
    def async_on_demand_update(self, online: bool) -> None:
        """Update state."""
        self.async_process_update(online)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register state update callback."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                signal_device_update(self._mac_address),
                self.async_on_demand_update,
            )
        )
