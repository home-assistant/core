"""Support for Renault number entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from renault_api.kamereon.models import KamereonVehicleBatterySocData

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RenaultConfigEntry
from .const import DOMAIN
from .entity import RenaultDataEntity, RenaultDataEntityDescription

# Coordinator is used to centralize the data updates
# but renault servers are unreliable and it's safer to queue action calls
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class RenaultNumberEntityDescription(
    NumberEntityDescription, RenaultDataEntityDescription
):
    """Class describing Renault number entities."""

    data_key: str


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RenaultConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Renault entities from config entry."""
    entities: list[RenaultNumberEntity] = [
        RenaultNumberEntity(vehicle, description)
        for vehicle in config_entry.runtime_data.vehicles.values()
        for description in NUMBER_TYPES
        if description.coordinator in vehicle.coordinators
    ]
    async_add_entities(entities)


class RenaultNumberEntity(
    RenaultDataEntity[KamereonVehicleBatterySocData], NumberEntity
):
    """Mixin for number specific attributes."""

    entity_description: RenaultNumberEntityDescription

    @property
    def native_value(self) -> float | None:
        """Return the entity value to represent the entity state."""
        return cast(float | None, self._get_data_attr(self.entity_description.data_key))

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        if (
            self.coordinator.data is None
            or (current_min := self.coordinator.data.socMin) is None
            or (current_target := self.coordinator.data.socTarget) is None
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="battery_soc_unavailable",
            )

        int_value = round(value)

        # Update the appropriate value based on which entity this is
       ​ if self.entity_description.key == "charge_limit_min":
            await self.vehicle.set_battery_soc(
                min_soc=int_value, target_soc=current_target
            )
            # Optimistically update local coordinator data so the new
            # limits are reflected immediately without a remote refresh.
            self.coordinator.data.socMin = int_value
        elif self.entity_description.key == "charge_limit_target":
            await self.vehicle.set_battery_soc(
                min_soc=current_min, target_soc=int_value
            )
            # Optimistically update local coordinator data so the new
            # limits are reflected immediately without a remote refresh.
            self.coordinator.data.socTarget = int_value
        else:
            raise NotImplementedError(
                f"Unsupported Renault number entity key: {self.entity_description.key}"
            )

        # Notify listeners about the updated SoC limits without triggering
        # a remote refresh, as Renault servers may still cache old values.
        await self.coordinator.async_set_updated_data(self.coordinator.data)
NUMBER_TYPES: tuple[RenaultNumberEntityDescription, ...] = (
    RenaultNumberEntityDescription(
        key="charge_limit_min",
        coordinator="battery_soc",
        data_key="socMin",
        device_class=NumberDeviceClass.BATTERY,
        native_min_value=15,
        native_max_value=45,
        native_step=5,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        translation_key="charge_limit_min",
    ),
    RenaultNumberEntityDescription(
        key="charge_limit_target",
        coordinator="battery_soc",
        data_key="socTarget",
        device_class=NumberDeviceClass.BATTERY,
        native_min_value=55,
        native_max_value=100,
        native_step=5,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        translation_key="charge_limit_target",
    ),
)
