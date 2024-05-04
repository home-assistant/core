"""Entity for Surepetcare."""

from __future__ import annotations

from abc import abstractmethod

from surepy.entities import SurepyEntity

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SurePetcareDataCoordinator
from .const import DOMAIN


class SurePetcareEntity(CoordinatorEntity[SurePetcareDataCoordinator]):
    """An implementation for Sure Petcare Entities."""

    def __init__(
        self,
        surepetcare_id: int,
        coordinator: SurePetcareDataCoordinator,
    ) -> None:
        """Initialize a Sure Petcare entity."""
        super().__init__(coordinator)

        self._id = surepetcare_id

        surepy_entity = coordinator.data[surepetcare_id]

        if surepy_entity.name:
            self._device_name = surepy_entity.name.capitalize()
        else:
            self._device_name = surepy_entity.type.name.capitalize().replace("_", " ")

        self._device_id = f"{surepy_entity.household_id}-{surepetcare_id}"
        self._attr_device_info = DeviceInfo(
            configuration_url="https://surepetcare.io/dashboard/",
            identifiers={(DOMAIN, self._device_id)},
            name=self._device_name,
            manufacturer="Sure Petcare",
            model=surepy_entity.type.name.capitalize().replace("_", " "),
        )
        self._update_attr(coordinator.data[surepetcare_id])

    @abstractmethod
    @callback
    def _update_attr(self, surepy_entity: SurepyEntity) -> None:
        """Update the state and attributes."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get the latest data and update the state."""
        self._update_attr(self.coordinator.data[self._id])
        self.async_write_ha_state()
