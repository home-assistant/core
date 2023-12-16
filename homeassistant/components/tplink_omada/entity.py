"""Base entity definitions."""
from typing import Generic, TypeVar

from tplink_omada_client.devices import OmadaDevice

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OmadaCoordinator

T = TypeVar("T")


class OmadaDeviceEntity(CoordinatorEntity[OmadaCoordinator[T]], Generic[T]):
    """Common base class for all entities associated with Omada SDN Devices."""

    def __init__(self, coordinator: OmadaCoordinator[T], device: OmadaDevice) -> None:
        """Initialize the device."""
        super().__init__(coordinator)
        self.device = device
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, device.mac)},
            identifiers={(DOMAIN, device.mac)},
            manufacturer="TP-Link",
            model=device.model_display_name,
            name=device.name,
        )
