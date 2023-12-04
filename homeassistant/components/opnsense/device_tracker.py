"""Device tracker support for OPNSense routers."""
from __future__ import annotations

import logging

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import OPNSenseDomainData
from .const import DOMAIN
from .coordinator import OPNSenseUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a OPNSense config entry."""

    data: OPNSenseDomainData = hass.data[DOMAIN]
    coordinator = data.coordinators[entry.entry_id]

    existing_macs = set()

    @callback
    def new_device_callback() -> None:
        entities = []
        for device_mac in coordinator.data:
            if device_mac in existing_macs:
                continue
            entities.append(OPNSenseScannerEntity(coordinator, device_mac))
            existing_macs.add(device_mac)

        async_add_entities(entities)

    # Register the update listener and call it
    entry.async_on_unload(coordinator.async_add_listener(new_device_callback))
    new_device_callback()


class OPNSenseScannerEntity(
    CoordinatorEntity[OPNSenseUpdateCoordinator], ScannerEntity
):
    """Representation of a Ping device tracker."""

    _mac: str

    def __init__(self, coordinator, mac_address) -> None:
        """Initialize a OPNSense client."""
        super().__init__(coordinator)
        self._mac = mac_address

    @property
    def ip_address(self) -> str | None:
        """Return the primary ip address of the device."""
        if not self.is_connected:
            return None
        return self.coordinator.data[self._mac].ip_address

    @property
    def mac_address(self) -> str | None:
        """Return the mac address of the device."""
        return self._mac

    @property
    def hostname(self) -> str | None:
        """Return hostname of the device."""
        if not self.is_connected:
            return None
        return self.coordinator.data[self._mac].hostname

    @property
    def name(self) -> str | None:
        """Return the name of the entity."""
        return self.name

    @property
    def _name(self) -> str:
        """Return the name of the entity."""
        return (
            self.is_connected and self.coordinator.data[self._mac].hostname or self._mac
        )

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return self._mac in self.coordinator.data

    @property
    def source_type(self) -> SourceType:
        """Return the source type which is router."""
        return SourceType.ROUTER

    # TODO Move this to allow users to add them manually? like Unifi or asuswrt
    # @property
    # def device_info(self) -> DeviceInfo:
    #     """Return the device info."""
    #     return DeviceInfo(
    #         connections={(CONNECTION_NETWORK_MAC, self._mac)},
    #         default_manufacturer=self.coordinator.data[self._mac].manufacturer,
    #         default_name=self._name,
    #     )
