"""Generic platform."""
from __future__ import annotations

from typing import TypeVar

from devolo_plc_api.device import Device
from devolo_plc_api.device_api import (
    ConnectedStationInfo,
    NeighborAPInfo,
    WifiGuestAccessGet,
)
from devolo_plc_api.plcnet_api import LogicalNetwork

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

_DataT = TypeVar(
    "_DataT",
    bound=(
        LogicalNetwork
        | list[ConnectedStationInfo]
        | list[NeighborAPInfo]
        | WifiGuestAccessGet
        | bool
    ),
)


class DevoloEntity(CoordinatorEntity[DataUpdateCoordinator[_DataT]]):
    """Representation of a devolo home network device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator[_DataT],
        device: Device,
    ) -> None:
        """Initialize a devolo home network device."""
        super().__init__(coordinator)

        self.device = device
        self.entry = entry

        self._attr_device_info = DeviceInfo(
            configuration_url=f"http://{device.ip}",
            identifiers={(DOMAIN, str(device.serial_number))},
            manufacturer="devolo",
            model=device.product,
            name=entry.title,
            sw_version=device.firmware_version,
        )
        self._attr_translation_key = self.entity_description.key
        self._attr_unique_id = f"{device.serial_number}_{self.entity_description.key}"
