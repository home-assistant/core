"""Base entity definitions."""

from typing import Any

from tplink_omada_client.devices import OmadaDevice

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OmadaControllerCoordinator, OmadaCoordinator


class OmadaControllerEntity(CoordinatorEntity[OmadaControllerCoordinator]):
    """Common base class for entities associated with an Omada controller."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: OmadaControllerCoordinator) -> None:
        """Initialize the controller entity."""
        super().__init__(coordinator)
        controller = coordinator.config_entry.runtime_data
        info = coordinator.data.info
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, controller.controller_id)},
            manufacturer="TP-Link",
            model=controller.controller_name,
            name=controller.controller_name,
            sw_version=info.controller_version,
        )


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
            via_device=(DOMAIN, coordinator.config_entry.runtime_data.controller_id),
        )
