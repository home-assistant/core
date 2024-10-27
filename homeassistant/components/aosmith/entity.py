"""The base entity for the A. O. Smith integration."""

from py_aosmith import AOSmithAPIClient
from py_aosmith.models import Device as AOSmithDevice

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AOSmithEnergyCoordinator, AOSmithStatusCoordinator


class AOSmithEntity[
    _AOSmithCoordinatorT: AOSmithStatusCoordinator | AOSmithEnergyCoordinator
](CoordinatorEntity[_AOSmithCoordinatorT]):
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
    def device(self) -> AOSmithDevice:
        """Shortcut to get the device from the coordinator data."""
        return self.coordinator.data[self.junction_id]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.device.status.is_online


class AOSmithEnergyEntity(AOSmithEntity[AOSmithEnergyCoordinator]):
    """Base entity for entities that use data from the energy coordinator."""

    @property
    def energy_usage(self) -> float:
        """Shortcut to get the energy usage from the coordinator data."""
        return self.coordinator.data[self.junction_id]
