"""Base entity definitions."""
from tplink_omada_client.devices import OmadaSwitch, OmadaSwitchPortDetails

from homeassistant.helpers import device_registry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OmadaCoordinator


class OmadaSwitchDeviceEntity(
    CoordinatorEntity[OmadaCoordinator[OmadaSwitchPortDetails]]
):
    """Common base class for all entities attached to Omada network switches."""

    def __init__(
        self, coordinator: OmadaCoordinator[OmadaSwitchPortDetails], device: OmadaSwitch
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.device = device

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about the device."""
        return DeviceInfo(
            connections={(device_registry.CONNECTION_NETWORK_MAC, self.device.mac)},
            identifiers={(DOMAIN, (self.device.mac))},
            manufacturer="TP-Link",
            model=self.device.model_display_name,
            name=self.device.name,
        )
