"""Support for Renault number entities."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, cast

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
    update_fn: Callable[[RenaultNumberEntity, float], Coroutine[Any, Any, None]]


async def _set_charge_limit_min(entity: RenaultNumberEntity, value: float) -> None:
    """Set the minimum SOC.

    The target SOC is required to set the minimum SOC, so we need to fetch it first.
    """
    if (data := entity.coordinator.data) is None or (
        target_soc := data.socTarget
    ) is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="battery_soc_unavailable",
        )
    await _set_charge_limits(entity, min_soc=round(value), target_soc=target_soc)


async def _set_charge_limit_target(entity: RenaultNumberEntity, value: float) -> None:
    """Set the target SOC.

    The minimum SOC is required to set the target SOC, so we need to fetch it first.
    """
    if (data := entity.coordinator.data) is None or (min_soc := data.socMin) is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="battery_soc_unavailable",
        )
    await _set_charge_limits(entity, min_soc=min_soc, target_soc=round(value))


async def _set_charge_limits(
    entity: RenaultNumberEntity, min_soc: int, target_soc: int
) -> None:
    """Set the minimum and target SOC.

    Optimistically update local coordinator data so the new
    limits are reflected immediately without a remote refresh,
    as Renault servers may still cache old values.
    """
    await entity.vehicle.set_battery_soc(min_soc=min_soc, target_soc=target_soc)

    entity.coordinator.data.socMin = min_soc
    entity.coordinator.data.socTarget = target_soc
    entity.coordinator.async_set_updated_data(entity.coordinator.data)


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
        await self.entity_description.update_fn(self, value)


NUMBER_TYPES: tuple[RenaultNumberEntityDescription, ...] = (
    RenaultNumberEntityDescription(
        key="charge_limit_min",
        coordinator="battery_soc",
        data_key="socMin",
        update_fn=_set_charge_limit_min,
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
        update_fn=_set_charge_limit_target,
        device_class=NumberDeviceClass.BATTERY,
        native_min_value=55,
        native_max_value=100,
        native_step=5,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        translation_key="charge_limit_target",
    ),
)
