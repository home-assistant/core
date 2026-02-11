"""The nuki component."""

from __future__ import annotations

from pynuki.device import NukiDevice

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NukiCoordinator
from .helpers import parse_id


class NukiEntity[_NukiDeviceT: NukiDevice](CoordinatorEntity[NukiCoordinator]):
    """An entity using CoordinatorEntity.

    The CoordinatorEntity class provides:
      should_poll
      async_update
      async_added_to_hass
      available

    """

    def __init__(self, coordinator: NukiCoordinator, nuki_device: _NukiDeviceT) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._nuki_device = nuki_device

    @property
    def device_info(self) -> DeviceInfo:
        """Device info for Nuki entities."""
        return DeviceInfo(
            identifiers={(DOMAIN, parse_id(self._nuki_device.nuki_id))},
            name=self._nuki_device.name,
            manufacturer="Nuki Home Solutions GmbH",
            model=self._nuki_device.device_model_str.capitalize(),
            sw_version=self._nuki_device.firmware_version,
            via_device=(DOMAIN, self.coordinator.bridge_id),
            serial_number=parse_id(self._nuki_device.nuki_id),
        )
