"""Base entity for Flow-it."""

from flow_it_api.client import FlowItVMCMachine

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FlowItCoordinator


class FlowItVmcEntity(CoordinatorEntity[FlowItCoordinator]):
    """Base entity for Flow-it."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FlowItCoordinator,
        vmc: FlowItVMCMachine,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.vmc = vmc
        self._attr_unique_id = f"{coordinator.data.name}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data.name)},
            name=coordinator.data.name,
            manufacturer="FLOW-IT",
            model="VMC",
            sw_version=coordinator.data.data.alert.version,
        )
