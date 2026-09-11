"""Base entity definitions."""

from typing import Any

from tplink_omada_client import OmadaControllerStatus
from tplink_omada_client.devices import OmadaDevice, OmadaSwitchPortDetails

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OmadaCoordinator, OmadaControllerStatusCoordinator


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


def get_switch_port_base_name(port: OmadaSwitchPortDetails) -> str:
    """Get display name for a switch port."""
    if port.name == f"Port{port.port}":
        return str(port.port)
    return f"{port.port} ({port.name})"


class OmadaControllerEntity(CoordinatorEntity[OmadaControllerStatusCoordinator]):
    """Common base class for entities associated with the Omada Controller."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: OmadaControllerStatusCoordinator) -> None:
        """Initialize the controller entity."""
        super().__init__(coordinator)

        controller: OmadaControllerStatus = coordinator.data

        device_name = (
            f"{controller.model} - {controller.name}"
            if controller.name
            else controller.model
        )

        self._attr_device_info = dr.DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, controller.mac)},
            identifiers={(DOMAIN, controller.mac)},
            manufacturer="TP-Link",
            model=controller.model,
            name=device_name,
            sw_version=controller.current_version,
        )
