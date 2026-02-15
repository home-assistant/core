"""Support for Renault number entities."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import cast

from renault_api.kamereon.models import (
    KamereonVehicleBatterySocActionData,
    KamereonVehicleBatterySocData,
)

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
from .renault_vehicle import RenaultVehicleProxy

# Coordinator is used to centralize the data updates
# but renault servers are unreliable and it's safer to queue action calls
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class RenaultNumberEntityDescription(
    NumberEntityDescription, RenaultDataEntityDescription
):
    """Class describing Renault number entities."""

    data_key: str
    set_value_fn: Callable[
        [RenaultVehicleProxy, int, int], Awaitable[KamereonVehicleBatterySocActionData]
    ]


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
        # Get current values from coordinator
        if self.coordinator.data is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="battery_soc_unavailable",
            )

        current_min = self.coordinator.data.socMin
        current_target = self.coordinator.data.socTarget

        # Validate both min and target values are available
        if current_min is None or current_target is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="battery_soc_unavailable",
            )

        int_value = round(value)

        # Update the appropriate value based on which entity this is
        if self.entity_description.key == "charge_limit_min":
            await self.entity_description.set_value_fn(
                self.vehicle, int_value, current_target
            )
        elif self.entity_description.key == "charge_limit_target":
            await self.entity_description.set_value_fn(
                self.vehicle, current_min, int_value
            )
        else:
            raise NotImplementedError(
                f"Unsupported Renault number entity key: {self.entity_description.key}"
            )

        # Request coordinator refresh to update the displayed value
        await self.coordinator.async_request_refresh()


NUMBER_TYPES: tuple[RenaultNumberEntityDescription, ...] = (
    RenaultNumberEntityDescription(
        key="charge_limit_min",
        coordinator="battery_soc",
        data_key="socMin",
        device_class=NumberDeviceClass.BATTERY,
        # name field is required to avoid entity ID collisions when multiple
        # number entities exist on the same device (without it, entities get
        # generic IDs like number.reg_zoe_40 and number.reg_zoe_40_2)
        name="Minimum charge level",
        native_min_value=15,
        native_max_value=45,
        native_step=5,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        translation_key="charge_limit_min",
        set_value_fn=lambda vehicle, min_val, target_val: vehicle.set_battery_soc(
            min_soc=min_val, target_soc=target_val
        ),
    ),
    RenaultNumberEntityDescription(
        key="charge_limit_target",
        coordinator="battery_soc",
        data_key="socTarget",
        device_class=NumberDeviceClass.BATTERY,
        # name field is required to generate stable entity IDs
        name="Target charge level",
        native_min_value=55,
        native_max_value=100,
        native_step=5,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        translation_key="charge_limit_target",
        set_value_fn=lambda vehicle, min_val, target_val: vehicle.set_battery_soc(
            min_soc=min_val, target_soc=target_val
        ),
    ),
)
