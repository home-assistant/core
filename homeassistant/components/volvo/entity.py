"""Volvo entity classes."""

from abc import abstractmethod
from dataclasses import dataclass

from volvocarsapi.models import VolvoCarsApiBaseModel

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import VolvoBaseCoordinator, VolvoConfigEntry


def get_unique_id(vin: str, key: str) -> str:
    """Get the unique ID."""
    return f"{vin}_{key}".lower()


def value_to_translation_key(value: str) -> str:
    """Make sure the translation key is valid."""
    return value.lower()


@dataclass(frozen=True, kw_only=True)
class VolvoEntityDescription(EntityDescription):
    """Describes a Volvo entity."""

    api_field: str | None = None


class VolvoBaseEntity(Entity):
    """Volvo base entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: VolvoConfigEntry,
        description: VolvoEntityDescription,
    ) -> None:
        """Initialize entity."""
        self.entity_description: VolvoEntityDescription = description
        self.entry = entry

        if description.device_class != SensorDeviceClass.BATTERY:
            self._attr_translation_key = description.key

        vehicle = entry.runtime_data.context.vehicle
        self._attr_unique_id = get_unique_id(vehicle.vin, description.key)

        model = (
            f"{vehicle.description.model} ({vehicle.model_year})"
            if vehicle.fuel_type == "NONE"
            else f"{vehicle.description.model} {vehicle.fuel_type} ({vehicle.model_year})"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vehicle.vin)},
            manufacturer=MANUFACTURER,
            model=model,
            model_id=f"{vehicle.description.model} ({vehicle.model_year})",
            name=f"{MANUFACTURER} {vehicle.description.model}",
            serial_number=vehicle.vin,
        )


class VolvoEntity(CoordinatorEntity[VolvoBaseCoordinator], VolvoBaseEntity):
    """Volvo base coordinator entity."""

    def __init__(
        self,
        coordinator: VolvoBaseCoordinator,
        description: VolvoEntityDescription,
    ) -> None:
        """Initialize entity."""
        CoordinatorEntity.__init__(self, coordinator)
        VolvoBaseEntity.__init__(self, coordinator.config_entry, description)

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
        if self.entity_description.api_field:
            api_field = self.coordinator.get_api_field(
                self.entity_description.api_field
            )
            return super().available and api_field is not None

        return super().available

    @abstractmethod
    def _update_state(self, api_field: VolvoCarsApiBaseModel | None) -> None:
        """Update the state of the entity."""
        raise NotImplementedError
