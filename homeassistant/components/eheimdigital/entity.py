"""Base entity for EHEIM Digital."""

from abc import abstractmethod

from eheimdigital.device import EheimDigitalDevice

from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EheimDigitalUpdateCoordinator


class EheimDigitalEntity[_DeviceT: EheimDigitalDevice](
    CoordinatorEntity[EheimDigitalUpdateCoordinator]
):
    """Represent a EHEIM Digital entity."""

    _attr_has_entity_name = True
    _device: _DeviceT
    _device_address: str

    def __init__(
        self, coordinator: EheimDigitalUpdateCoordinator, device: _DeviceT
    ) -> None:
        """Initialize a EHEIM Digital entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            configuration_url="http://eheimdigital.local",
            name=device.name,
            connections={(CONNECTION_NETWORK_MAC, device.mac_address)},
            manufacturer="EHEIM",
            model=device.device_type.model_name,
            identifiers={(DOMAIN, device.mac_address)},
            suggested_area=device.aquarium_name,
            sw_version=device.sw_version,
            via_device=(DOMAIN, coordinator.hub.master.mac_address),
        )
        self._device = device
        self._device_address = device.mac_address

    @abstractmethod
    def _async_update_attrs(self) -> None: ...  # pragma: no cover

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        self._async_update_attrs()
        super()._handle_coordinator_update()
