"""The base entity for the A. O. Smith integration."""
from typing import TypeVar

from py_aosmith import AOSmithAPIClient

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AOSmithEnergyCoordinator, AOSmithStatusCoordinator

_AOSmithCoordinatorT = TypeVar(
    "_AOSmithCoordinatorT", bound=AOSmithStatusCoordinator | AOSmithEnergyCoordinator
)


class AOSmithEntity(CoordinatorEntity[_AOSmithCoordinatorT]):
    """Base entity for A. O. Smith."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: _AOSmithCoordinatorT, junction_id: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.junction_id = junction_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, junction_id)},
        )

    @property
    def client(self) -> AOSmithAPIClient:
        """Shortcut to get the API client."""
        return self.coordinator.client


class AOSmithStatusEntity(AOSmithEntity[AOSmithStatusCoordinator]):
    """Base entity for entities that use data from the status coordinator."""

    @property
    def device(self):
        """Shortcut to get the device status from the coordinator data."""
        return self.coordinator.data.get(self.junction_id)

    @property
    def device_data(self):
        """Shortcut to get the device data within the device status."""
        device = self.device
        return None if device is None else device.get("data", {})

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.device_data.get("isOnline") is True


class AOSmithEnergyEntity(AOSmithEntity[AOSmithEnergyCoordinator]):
    """Base entity for entities that use data from the energy coordinator."""

    @property
    def energy_usage(self) -> float | None:
        """Shortcut to get the energy usage from the coordinator data."""
        return self.coordinator.data.get(self.junction_id)
