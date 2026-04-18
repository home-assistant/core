"""Support for Renault sensors."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from renault_api.kamereon.models import (
    KamereonVehicleChargeModeData,
    KamereonVehicleDataAttributes,
)

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RenaultConfigEntry
from .entity import RenaultDataEntity, RenaultDataEntityDescription

# Coordinator is used to centralize the data updates
# but renault servers are unreliable and it's safer to queue action calls
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class RenaultSelectEntityDescription[T: KamereonVehicleDataAttributes](
    SelectEntityDescription, RenaultDataEntityDescription
):
    """Class describing Renault select entities."""

    value_fn: Callable[[RenaultSelectEntity[T]], str | None]
    update_fn: Callable[[RenaultSelectEntity[T], str], Coroutine[Any, Any, Any]]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RenaultConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Renault entities from config entry."""
    entities: list[RenaultSelectEntity] = [
        RenaultSelectEntity(vehicle, description)
        for vehicle in config_entry.runtime_data.vehicles.values()
        for description in SENSOR_TYPES
        if description.coordinator in vehicle.coordinators
    ]
    async_add_entities(entities)


class RenaultSelectEntity[T: KamereonVehicleDataAttributes](
    RenaultDataEntity[T], SelectEntity
):
    """Mixin for sensor specific attributes."""

    entity_description: RenaultSelectEntityDescription[T]

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return self.entity_description.value_fn(self)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.update_fn(self, option)


SENSOR_TYPES: tuple[RenaultSelectEntityDescription, ...] = (
    RenaultSelectEntityDescription[KamereonVehicleChargeModeData](
        key="charge_mode",
        coordinator="charge_mode",
        translation_key="charge_mode",
        options=["always", "always_charging", "schedule_mode", "scheduled"],
        update_fn=lambda e, option: e.vehicle.set_charge_mode(option),
        value_fn=lambda e: e.coordinator.data.chargeMode,
    ),
)
