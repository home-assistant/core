"""Support for Renault sensors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from renault_api.kamereon.models import KamereonVehicleBatteryStatusData

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import RenaultConfigEntry
from .entity import RenaultDataEntity, RenaultDataEntityDescription

# Coordinator is used to centralize the data updates
# but renault servers are unreliable and it's safer to queue action calls
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class RenaultSelectEntityDescription(
    SelectEntityDescription, RenaultDataEntityDescription
):
    """Class describing Renault select entities."""

    data_key: str


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RenaultConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Renault entities from config entry."""
    entities: list[RenaultSelectEntity] = [
        RenaultSelectEntity(vehicle, description)
        for vehicle in config_entry.runtime_data.vehicles.values()
        for description in SENSOR_TYPES
        if description.coordinator in vehicle.coordinators
    ]
    async_add_entities(entities)


class RenaultSelectEntity(
    RenaultDataEntity[KamereonVehicleBatteryStatusData], SelectEntity
):
    """Mixin for sensor specific attributes."""

    entity_description: RenaultSelectEntityDescription

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return cast(str, self.data)

    @property
    def data(self) -> StateType:
        """Return the state of this entity."""
        return self._get_data_attr(self.entity_description.data_key)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.vehicle.set_charge_mode(option)


SENSOR_TYPES: tuple[RenaultSelectEntityDescription, ...] = (
    RenaultSelectEntityDescription(
        key="charge_mode",
        coordinator="charge_mode",
        data_key="chargeMode",
        translation_key="charge_mode",
        options=["always", "always_charging", "schedule_mode", "scheduled"],
    ),
)
