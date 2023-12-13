"""The base entity for the A. O. Smith integration."""
from typing import TypeVar

from py_aosmith import AOSmithAPIClient

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AOSmithEnergyCoordinator, AOSmithStatusCoordinator
from .models import AOSmithDeviceDetails

_AOSmithCoordinatorT = TypeVar(
    "_AOSmithCoordinatorT", bound=AOSmithStatusCoordinator | AOSmithEnergyCoordinator
)


class AOSmithEntity(CoordinatorEntity[_AOSmithCoordinatorT]):
    """Base entity for A. O. Smith."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: _AOSmithCoordinatorT,
        device_details: AOSmithDeviceDetails,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.device_details = device_details

        self._attr_device_info = DeviceInfo(
            manufacturer="A. O. Smith",
            name=device_details.name,
            model=device_details.model,
            serial_number=device_details.serial_number,
            suggested_area=device_details.install_location,
            identifiers={(DOMAIN, device_details.junction_id)},
            sw_version=device_details.firmware_version,
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
        return self.coordinator.data.get(self.device_details.junction_id)

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
        return self.coordinator.data.get(self.device_details.junction_id)
