"""Base entity definitions."""

from typing import Any

from tplink_omada_client import OmadaControllerInfo
from tplink_omada_client.devices import OmadaDevice

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OmadaCoordinator


class OmadaDeviceEntity[_T: OmadaCoordinator[Any]](CoordinatorEntity[_T]):
    """Common base class for all entities associated with Omada SDN Devices."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: _T, device: OmadaDevice) -> None:
        """Initialize the device."""
        super().__init__(coordinator)
        self.device = device
        self._attr_device_info = dr.DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, device.mac)},
            identifiers={(DOMAIN, device.mac)},
            manufacturer="TP-Link",
            model=device.model_display_name,
            name=device.name,
        )


def controller_device_info(controller_info: OmadaControllerInfo) -> dr.DeviceInfo:
    """Return device info for the Omada controller."""
    return dr.DeviceInfo(
        identifiers={(DOMAIN, controller_info.omadac_id)},
        manufacturer="TP-Link",
        model="Omada Controller",
        name="Omada Controller",
        sw_version=controller_info.controller_version,
    )
