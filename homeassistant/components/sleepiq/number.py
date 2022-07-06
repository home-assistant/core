"""Support for SleepIQ SleepNumber firmness number entities."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, cast

from asyncsleepiq import SleepIQActuator, SleepIQBed, SleepIQSleeper

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import ACTUATOR, DOMAIN, ENTITY_TYPES, FIRMNESS, ICON_OCCUPIED
from .coordinator import SleepIQData
from .entity import SleepIQBedEntity


@dataclass
class SleepIQNumberEntityDescriptionMixin:
    """Mixin to describe a SleepIQ number entity."""

    value_fn: Callable[[Any], float]
    set_value_fn: Callable[[Any, int], Coroutine[None, None, None]]
    get_name_fn: Callable[[SleepIQBed, Any], str]
    get_unique_id_fn: Callable[[SleepIQBed, Any], str]


@dataclass
class SleepIQNumberEntityDescription(
    NumberEntityDescription, SleepIQNumberEntityDescriptionMixin
):
    """Class to describe a SleepIQ number entity."""


async def _async_set_firmness(sleeper: SleepIQSleeper, firmness: int) -> None:
    await sleeper.set_sleepnumber(firmness)


async def _async_set_actuator_position(
    actuator: SleepIQActuator, position: int
) -> None:
    await actuator.set_position(position)


def _get_actuator_name(bed: SleepIQBed, actuator: SleepIQActuator) -> str:
    if actuator.side:
        return f"SleepNumber {bed.name} {actuator.side_full} {actuator.actuator_full} {ENTITY_TYPES[ACTUATOR]}"

    return f"SleepNumber {bed.name} {actuator.actuator_full} {ENTITY_TYPES[ACTUATOR]}"


def _get_actuator_unique_id(bed: SleepIQBed, actuator: SleepIQActuator) -> str:
    if actuator.side:
        return f"{bed.id}_{actuator.side}_{actuator.actuator}"

    return f"{bed.id}_{actuator.actuator}"


def _get_sleeper_name(bed: SleepIQBed, sleeper: SleepIQSleeper) -> str:
    return f"SleepNumber {bed.name} {sleeper.name} {ENTITY_TYPES[FIRMNESS]}"


def _get_sleeper_unique_id(bed: SleepIQBed, sleeper: SleepIQSleeper) -> str:
    return f"{sleeper.sleeper_id}_{FIRMNESS}"


NUMBER_DESCRIPTIONS: dict[str, SleepIQNumberEntityDescription] = {
    FIRMNESS: SleepIQNumberEntityDescription(
        key=FIRMNESS,
        native_min_value=5,
        native_max_value=100,
        native_step=5,
        name=ENTITY_TYPES[FIRMNESS],
        icon=ICON_OCCUPIED,
        value_fn=lambda sleeper: cast(float, sleeper.sleep_number),
        set_value_fn=_async_set_firmness,
        get_name_fn=_get_sleeper_name,
        get_unique_id_fn=_get_sleeper_unique_id,
    ),
    ACTUATOR: SleepIQNumberEntityDescription(
        key=ACTUATOR,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        name=ENTITY_TYPES[ACTUATOR],
        icon=ICON_OCCUPIED,
        value_fn=lambda actuator: cast(float, actuator.position),
        set_value_fn=_async_set_actuator_position,
        get_name_fn=_get_actuator_name,
        get_unique_id_fn=_get_actuator_unique_id,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SleepIQ bed sensors."""
    data: SleepIQData = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for bed in data.client.beds.values():
        for sleeper in bed.sleepers:
            entities.append(
                SleepIQNumberEntity(
                    data.data_coordinator,
                    bed,
                    sleeper,
                    NUMBER_DESCRIPTIONS[FIRMNESS],
                )
            )
        for actuator in bed.foundation.actuators:
            entities.append(
                SleepIQNumberEntity(
                    data.data_coordinator,
                    bed,
                    actuator,
                    NUMBER_DESCRIPTIONS[ACTUATOR],
                )
            )

    async_add_entities(entities)


class SleepIQNumberEntity(SleepIQBedEntity, NumberEntity):
    """Representation of a SleepIQ number entity."""

    entity_description: SleepIQNumberEntityDescription
    _attr_icon = "mdi:bed"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        bed: SleepIQBed,
        device: Any,
        description: SleepIQNumberEntityDescription,
    ) -> None:
        """Initialize the number."""
        self.entity_description = description
        self.device = device

        self._attr_name = description.get_name_fn(bed, device)
        self._attr_unique_id = description.get_unique_id_fn(bed, device)

        super().__init__(coordinator, bed)

    @callback
    def _async_update_attrs(self) -> None:
        """Update number attributes."""
        self._attr_native_value = float(self.entity_description.value_fn(self.device))

    async def async_set_native_value(self, value: float) -> None:
        """Set the number value."""
        await self.entity_description.set_value_fn(self.device, int(value))
        self._attr_native_value = value
        self.async_write_ha_state()
