"""Support for Bbox routers."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from aiobbox.models import Host

from homeassistant.components.device_tracker import (
    ATTR_HOST_NAME,
    ATTR_IP,
    ATTR_MAC,
    ScannerEntity,
    SourceType,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import _LOGGER
from .coordinator import BboxRouter

if TYPE_CHECKING:
    from . import BboxConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Bbox device tracker entries."""
    coordinator: BboxRouter = entry.runtime_data

    tracked: set[str] = set()

    @callback
    def _async_update_devices() -> None:
        """Update existing entities and add new ones."""
        new_entities = []
        for mac, device in coordinator.data.connected_devices.items():
            if mac in tracked:
                continue

            new_entities.append(BboxDeviceTracker(coordinator, device))
            tracked.add(mac)
            _LOGGER.debug("New device tracker: %s", device.hostname or mac)

        async_add_entities(new_entities)

    # Add initial devices
    _async_update_devices()

    # Listen for device updates
    entry.async_on_unload(coordinator.async_add_listener(_async_update_devices))


class BboxDeviceTracker(CoordinatorEntity[BboxRouter], ScannerEntity):
    """Representation of a Bbox device."""

    _attr_translation_key = "device_tracker"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BboxRouter,
        device: Host,
    ) -> None:
        """Initialize a Bbox device."""
        super().__init__(coordinator)

        self.mac = device.macaddress

        # Use MAC address as unique ID for persistence
        self._attr_unique_id = self.mac
        self._attr_name = self.hostname or self.mac

    @property
    def base_attributes(self) -> dict[str, str | None]:
        """The bare minimum attributes a device will always have."""
        attrs: dict[str, str | None] = {
            ATTR_MAC: self.mac_address,
            ATTR_IP: self.ip_address,
        }
        if self.hostname:
            attrs[ATTR_HOST_NAME] = self.hostname
        return attrs

    @property
    def source_type(self) -> SourceType:
        """Return the source type."""
        return SourceType.ROUTER

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return self.coordinator.data.connected_devices[self.mac].active

    @property
    def ip_address(self) -> str:
        """Return the primary ip address of the device."""
        return self.coordinator.data.connected_devices[self.mac].ipaddress

    @property
    def hostname(self) -> str | None:
        """Return the hostname."""
        device = self.coordinator.data.connected_devices[self.mac]
        return (
            device.hostname
            or device.informations.model  # codespell:ignore informations
        )

    @property
    def mac_address(self) -> str:
        """Return the MAC address."""
        return self.mac

    @property
    def extra_state_attributes(self) -> dict[str, str | int | bool | datetime]:
        """Return extra attributes."""
        device = self.coordinator.data.connected_devices[self.mac]

        ipv6_addresses: list[str] = []
        if device.ip6address:
            ipv6_addresses = [
                ip6.ipaddress for ip6 in device.ip6address if ip6.ipaddress
            ]
        device_info = device.informations  # codespell:ignore informations
        wireless_info = device.wireless

        attributes = self.base_attributes | {
            "device_type": device.devicetype,
            "ip_assignment": device.type,  # Static or DHCP
            "link_type": device.link,  # Wifi 2.4, Wifi 5, Ethernet, etc.
            "ipv6_addresses": ", ".join(ipv6_addresses) if ipv6_addresses else "",
            "device_category": device_info.type,
            "manufacturer": device_info.manufacturer,
            "device_model": device_info.model,
            "operating_system": device_info.operatingSystem,
            "wireless_band": wireless_info.band,
            "signal_strength": wireless_info.rssi0,
            "estimated_rate": wireless_info.estimatedRate,
            "first_seen": device.firstseen,
            "last_seen": device.lastseen,
            "guest_device": device.guest,
        }
        # Remove None values to keep attributes clean
        return {k: v for k, v in attributes.items() if v}
