"""Base entity for the Moulinex integration."""

from typing import override

from aiomoulinex import Appliance, ApplianceState

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MoulinexDataUpdateCoordinator


class MoulinexEntity(CoordinatorEntity[MoulinexDataUpdateCoordinator]):
    """Base class for the entities of a Moulinex appliance."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MoulinexDataUpdateCoordinator,
        appliance: Appliance,
        key: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.appliance = appliance
        self._attr_unique_id = f"{appliance.thing_uuid}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, appliance.thing_uuid)},
            manufacturer=coordinator.manufacturer,
            model=appliance.model,
            model_id=appliance.cmmf,
            name=appliance.name,
            serial_number=appliance.thing_uuid,
            sw_version=self.appliance_state.shadow.firmware.ui_version,
        )

    @property
    def appliance_state(self) -> ApplianceState:
        """Return the latest state of the appliance."""
        return self.coordinator.data[self.appliance.thing_uuid]

    @property
    @override
    def available(self) -> bool:
        """Return if the appliance is reachable through the cloud."""
        return (
            super().available
            and self.coordinator.client.connected
            and self.appliance.thing_uuid in self.coordinator.data
            and self.appliance_state.shadow.connected is True
        )
