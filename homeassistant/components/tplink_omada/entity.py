"""Base entity definitions."""

from typing import TYPE_CHECKING, Any

from tplink_omada_client.definitions import (
    OmadaControllerInfo,
    OmadaControllerStatus,
    OmadaControllerType,
)
from tplink_omada_client.devices import OmadaDevice, OmadaSwitchPortDetails

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN
from .coordinator import OmadaCoordinator

if TYPE_CHECKING:
    from . import OmadaConfigEntry


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


def controller_device_identifier(config_entry: "OmadaConfigEntry") -> str:
    """Return the controller device identifier for a config entry."""
    return f"controller_{config_entry.unique_id or config_entry.entry_id}"


def controller_device_model(controller_type: OmadaControllerType) -> str:
    """Return the model description for an Omada controller."""
    if controller_type.is_soft_controller:
        return "Omada Controller Software"

    return "Omada Controller Hardware"


class OmadaControllerEntity[_T: DataUpdateCoordinator[Any]](
    CoordinatorEntity[_T]
):
    """Common base class for entities associated with an Omada controller."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: _T,
        config_entry: "OmadaConfigEntry",
        controller_info: OmadaControllerInfo,
        controller_type: OmadaControllerType,
        controller_status: OmadaControllerStatus,
        controller_name: str,
    ) -> None:
        """Initialize the controller entity."""
        super().__init__(coordinator)

        self._attr_device_info = dr.DeviceInfo(
            identifiers={
                (DOMAIN, controller_device_identifier(config_entry))
            },
            connections={
                (dr.CONNECTION_NETWORK_MAC, controller_status.mac_address)
            },
            manufacturer="TP-Link",
            model=controller_device_model(controller_type),
            name=controller_name,
            sw_version=controller_info.controller_version,
        )
