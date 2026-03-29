"""Device tracker support for OPNsense routers."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from aioopnsense import OPNsenseApiError

from homeassistant.components.device_tracker import ScannerEntity, SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=120)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker for OPNsense."""
    client = config_entry.runtime_data["client"]
    tracker_interfaces: list[str] = config_entry.runtime_data["tracker_interfaces"]

    tracked: dict[str, OPNsenseDevice] = {}
    update_lock = asyncio.Lock()

    async def _async_update_devices(_now: Any = None) -> None:
        """Update devices from OPNsense ARP table."""
        if update_lock.locked():
            return

        async with update_lock:
            try:
                devices = await client.get_arp()
            except OPNsenseApiError:
                _LOGGER.exception("Error fetching OPNsense ARP table")
                return

            new_entities: list[OPNsenseDevice] = []
            seen_macs: set[str] = set()

            for device in devices:
                if (
                    tracker_interfaces
                    and device.get("intf_description") not in tracker_interfaces
                ):
                    continue

                mac = device.get("mac")
                if not mac:
                    continue

                seen_macs.add(mac)

                if mac in tracked:
                    tracked[mac].update_from_arp(device)
                else:
                    entity = OPNsenseDevice(device)
                    tracked[mac] = entity
                    new_entities.append(entity)

            # Mark devices not in ARP table as not connected
            for mac, entity in tracked.items():
                if mac not in seen_macs:
                    entity.mark_disconnected()

            if new_entities:
                async_add_entities(new_entities)

    # Initial scan
    await _async_update_devices()

    # Schedule periodic scans and cancel on unload
    config_entry.async_on_unload(
        async_track_time_interval(hass, _async_update_devices, SCAN_INTERVAL)
    )


class OPNsenseDevice(ScannerEntity):
    """Representation of a device tracked via OPNsense."""

    _attr_source_type = SourceType.ROUTER

    def __init__(self, device: dict[str, Any]) -> None:
        """Initialize the device."""
        self._mac: str = device["mac"]
        self._attr_hostname = device.get("hostname") or None
        self._attr_ip_address = device.get("ip")
        self._attr_mac_address = self._mac
        self._is_connected = True
        self._manufacturer = device.get("manufacturer")

        # Use hostname or MAC as display name
        name = self._attr_hostname or self._mac.replace(":", "_")
        self._attr_name = name

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this device."""
        return self._mac

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return self._is_connected

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs: dict[str, Any] = {}
        if self._manufacturer:
            attrs["manufacturer"] = self._manufacturer
        return attrs

    @callback
    def update_from_arp(self, device: dict[str, Any]) -> None:
        """Update device data from ARP entry."""
        self._is_connected = True
        self._attr_hostname = device.get("hostname") or None
        self._attr_ip_address = device.get("ip")
        self._manufacturer = device.get("manufacturer")
        self.async_write_ha_state()

    @callback
    def mark_disconnected(self) -> None:
        """Mark device as not connected."""
        if self._is_connected:
            self._is_connected = False
            self.async_write_ha_state()
