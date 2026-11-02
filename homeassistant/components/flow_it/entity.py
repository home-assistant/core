"""Base entity for AriaQ."""

from flow_it_api.client import FlowItVMCMachine

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AriaQCoordinator


class AriaQVmcEntity(CoordinatorEntity[AriaQCoordinator]):
    """Base entity for AriaQ."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AriaQCoordinator,
        vmc: FlowItVMCMachine,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self.vmc = vmc
        self._attr_unique_id = f"{coordinator.data.state.name}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data.state.name)},
            name=coordinator.data.state.name,
            manufacturer="AriaQ",
            model="VMC",
            sw_version=coordinator.data.state.data.alert.version,
        )
