"""Device tracker support for OPNsense routers."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.device_tracker import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_OPNSENSE_CLIENT, CONF_TRACKER_INTERFACES
from .coordinator import OPNsenseDeviceTrackerCoordinator
from .types import DeviceDetails

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker for OPNsense component."""
    client = entry.runtime_data[CONF_OPNSENSE_CLIENT]
    interfaces = entry.runtime_data.get(CONF_TRACKER_INTERFACES, [])

    coordinator = OPNsenseDeviceTrackerCoordinator(hass, entry, client, interfaces)

    # Initial data fetch
    await coordinator.async_config_entry_first_refresh()

    entities = []
    if coordinator.data:
        for mac_address in coordinator.data:
            entity = OPNsenseDeviceTrackerEntity(coordinator, mac_address)
            coordinator.tracked_devices[mac_address] = entity
            entities.append(entity)

    async_add_entities(entities)


class OPNsenseDeviceTrackerEntity(CoordinatorEntity, ScannerEntity):
    """Representation of a tracked device."""

    _attr_should_poll = False
    _attr_translation_key = "device_tracker"

    def __init__(
        self,
        coordinator: OPNsenseDeviceTrackerCoordinator,
        mac_address: str,
    ) -> None:
        """Initialize the device tracker entity."""
        super().__init__(coordinator)
        self._mac_address = mac_address
        self._attr_unique_id = mac_address

    @property
    def device_data(self) -> DeviceDetails | None:
        """Return device data for current device."""
        if self.coordinator.data and self._mac_address in self.coordinator.data:
            return self.coordinator.data[self._mac_address]  # type: ignore[no-any-return]
        return None

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return (
            self.coordinator.data is not None
            and self._mac_address in self.coordinator.data
        )

    @property
    def name(self) -> str:
        """Return device name."""
        device_data = self.device_data
        if device_data and device_data.get("hostname"):
            return str(device_data["hostname"])
        return f"OPNsense Device {self._mac_address}"

    @property
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        return self._mac_address

    @property
    def ip_address(self) -> str | None:
        """Return the primary IP address of the device."""
        device_data = self.device_data
        if device_data:
            return device_data.get("ip")
        return None

    @property
    def hostname(self) -> str | None:
        """Return hostname of the device."""
        device_data = self.device_data
        if device_data:
            return device_data.get("hostname")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        device_data = self.device_data
        if not device_data:
            return {}

        attrs = {}
        if manufacturer := device_data.get("manufacturer"):
            attrs["manufacturer"] = manufacturer
        if interface := device_data.get("intf_description"):
            attrs["interface"] = interface
        if expires := device_data.get("expires"):
            attrs["expires"] = expires

        return attrs
