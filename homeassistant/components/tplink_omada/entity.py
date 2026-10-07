"""Base entity definitions."""

from typing import Any, override

from tplink_omada_client import OmadaControllerStatus
from tplink_omada_client.devices import OmadaDevice, OmadaSwitchPortDetails

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OmadaControllerStatusCoordinator, OmadaCoordinator


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
        self._controller_identifier = (DOMAIN, controller.mac)

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

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated controller status data."""
        device_registry = dr.async_get(self.hass)
        controller = self.coordinator.data
        device_entry = device_registry.async_get_device_by_identifier(
            self._controller_identifier,
            self.coordinator.config_entry.entry_id,
        )
        if (
            device_entry is not None
            and device_entry.sw_version != controller.current_version
        ):
            device_registry.async_update_device(
                device_entry.id,
                sw_version=controller.current_version,
            )

        super()._handle_coordinator_update()
