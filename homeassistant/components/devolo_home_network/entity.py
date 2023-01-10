"""Generic platform."""
from __future__ import annotations

from typing import TypeVar, Union

from devolo_plc_api.device import Device
from devolo_plc_api.device_api import ConnectedStationInfo, NeighborAPInfo
from devolo_plc_api.plcnet_api import LogicalNetwork

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

_DataT = TypeVar(
    "_DataT",
    bound=Union[
        LogicalNetwork,
        list[ConnectedStationInfo],
        list[NeighborAPInfo],
    ],
)


class DevoloEntity(CoordinatorEntity[DataUpdateCoordinator[_DataT]]):
    """Representation of a devolo home network device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[_DataT],
        device: Device,
        device_name: str,
    ) -> None:
        """Initialize a devolo home network device."""
        super().__init__(coordinator)

        self.device = device

        self._attr_device_info = DeviceInfo(
            configuration_url=f"http://{device.ip}",
            identifiers={(DOMAIN, str(device.serial_number))},
            manufacturer="devolo",
            model=device.product,
            name=device_name,
            sw_version=device.firmware_version,
        )
        self._attr_unique_id = f"{device.serial_number}_{self.entity_description.key}"
