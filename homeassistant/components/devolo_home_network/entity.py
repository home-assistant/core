"""Generic platform."""
from __future__ import annotations

from typing import TypeVar

from devolo_plc_api.device import Device
from devolo_plc_api.device_api import (
    ConnectedStationInfo,
    NeighborAPInfo,
    WifiGuestAccessGet,
)
from devolo_plc_api.plcnet_api import DataRate, LogicalNetwork

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

_DataT = TypeVar(
    "_DataT",
    bound=(
        LogicalNetwork
        | DataRate
        | list[ConnectedStationInfo]
        | list[NeighborAPInfo]
        | WifiGuestAccessGet
        | bool
    ),
)


class DevoloEntity(Entity):
    """Representation of a devolo home network device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        device: Device,
    ) -> None:
        """Initialize a devolo home network device."""
        self.device = device
        self.entry = entry

        self._attr_device_info = DeviceInfo(
            configuration_url=f"http://{device.ip}",
            connections={(CONNECTION_NETWORK_MAC, device.mac)},
            identifiers={(DOMAIN, str(device.serial_number))},
            manufacturer="devolo",
            model=device.product,
            serial_number=device.serial_number,
            sw_version=device.firmware_version,
        )
        self._attr_translation_key = self.entity_description.key
        self._attr_unique_id = f"{device.serial_number}_{self.entity_description.key}"


class DevoloCoordinatorEntity(
    CoordinatorEntity[DataUpdateCoordinator[_DataT]], DevoloEntity
):
    """Representation of a coordinated devolo home network device."""

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator[_DataT],
        device: Device,
    ) -> None:
        """Initialize a devolo home network device."""
        super().__init__(coordinator)
        DevoloEntity.__init__(self, entry, device)
