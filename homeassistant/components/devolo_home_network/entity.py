"""Generic platform."""

from __future__ import annotations

from devolo_plc_api.device_api import (
    ConnectedStationInfo,
    NeighborAPInfo,
    WifiGuestAccessGet,
)
from devolo_plc_api.plcnet_api import DataRate, LogicalNetwork

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import DevoloHomeNetworkConfigEntry
from .const import DOMAIN

type _DataType = (
    LogicalNetwork
    | DataRate
    | list[ConnectedStationInfo]
    | list[NeighborAPInfo]
    | WifiGuestAccessGet
    | bool
)


class DevoloEntity(Entity):
    """Representation of a devolo home network device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: DevoloHomeNetworkConfigEntry,
    ) -> None:
        """Initialize a devolo home network device."""
        self.device = entry.runtime_data.device
        self.entry = entry

        self._attr_device_info = DeviceInfo(
            configuration_url=f"http://{self.device.ip}",
            connections={(CONNECTION_NETWORK_MAC, self.device.mac)},
            identifiers={(DOMAIN, str(self.device.serial_number))},
            manufacturer="devolo",
            model=self.device.product,
            model_id=self.device.mt_number,
            serial_number=self.device.serial_number,
            sw_version=self.device.firmware_version,
        )
        self._attr_translation_key = self.entity_description.key
        self._attr_unique_id = (
            f"{self.device.serial_number}_{self.entity_description.key}"
        )


class DevoloCoordinatorEntity[_DataT: _DataType](
    CoordinatorEntity[DataUpdateCoordinator[_DataT]], DevoloEntity
):
    """Representation of a coordinated devolo home network device."""

    def __init__(
        self,
        entry: DevoloHomeNetworkConfigEntry,
        coordinator: DataUpdateCoordinator[_DataT],
    ) -> None:
        """Initialize a devolo home network device."""
        super().__init__(coordinator)
        DevoloEntity.__init__(self, entry)
