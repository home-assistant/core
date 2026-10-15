"""The nuki component."""

from typing import override

from pynuki.device import NukiDevice

from homeassistant.helpers import device_registry as dr
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
    @override
    def device_info(self) -> DeviceInfo:
        """Device info for Nuki entities."""
        return DeviceInfo(
            identifiers={(DOMAIN, parse_id(self._nuki_device.nuki_id))},
            name=self._nuki_device.name,
            manufacturer="Nuki Home Solutions GmbH",
            model=self._nuki_device.device_model_str.capitalize(),
            sw_version=self._nuki_device.firmware_version,
            via_device_id=dr.async_get_device_id_by_identifier(
                self.coordinator.hass,
                (DOMAIN, self.coordinator.bridge_id),
                config_entry_id=self.coordinator.config_entry.entry_id,
            ),
            serial_number=parse_id(self._nuki_device.nuki_id),
        )
