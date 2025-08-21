"""Volvo entity classes."""

from abc import abstractmethod
from dataclasses import dataclass

from volvocarsapi.models import VolvoCarsApiBaseModel

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_VIN, DOMAIN, MANUFACTURER
from .coordinator import VolvoBaseCoordinator


def get_unique_id(vin: str, key: str) -> str:
    """Get the unique ID."""
    return f"{vin}_{key}".lower()


def value_to_translation_key(value: str) -> str:
    """Make sure the translation key is valid."""
    return value.lower()


@dataclass(frozen=True, kw_only=True)
class VolvoEntityDescription(EntityDescription):
    """Describes a Volvo entity."""

    api_field: str


class VolvoEntity(CoordinatorEntity[VolvoBaseCoordinator]):
    """Volvo base entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: VolvoBaseCoordinator,
        description: VolvoEntityDescription,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator)

        self.entity_description: VolvoEntityDescription = description

        if description.device_class != SensorDeviceClass.BATTERY:
            self._attr_translation_key = description.key

        self._attr_unique_id = get_unique_id(
            coordinator.config_entry.data[CONF_VIN], description.key
        )

        vehicle = coordinator.vehicle
        model = (
            f"{vehicle.description.model} ({vehicle.model_year})"
            if vehicle.fuel_type == "NONE"
            else f"{vehicle.description.model} {vehicle.fuel_type} ({vehicle.model_year})"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vehicle.vin)},
            manufacturer=MANUFACTURER,
            model=model,
            name=f"{MANUFACTURER} {vehicle.description.model}",
            serial_number=vehicle.vin,
        )

        self._update_state(coordinator.get_api_field(description.api_field))

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        api_field = self.coordinator.get_api_field(self.entity_description.api_field)
        self._update_state(api_field)
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        api_field = self.coordinator.get_api_field(self.entity_description.api_field)
        return super().available and api_field is not None

    @abstractmethod
    def _update_state(self, api_field: VolvoCarsApiBaseModel | None) -> None:
        """Update the state of the entity."""
        raise NotImplementedError
