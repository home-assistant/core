"""Support for using number with ecobee thermostats."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EcobeeData
from .const import DOMAIN
from .entity import EcobeeBaseEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class EcobeeNumberEntityDescriptionBase:
    """Required values when describing Ecobee number entities."""

    mode: str
    ecobee_setting_key: str
    set_fn: Callable[[EcobeeData, int, int], Awaitable]


@dataclass
class EcobeeNumberEntityDescription(
    NumberEntityDescription, EcobeeNumberEntityDescriptionBase
):
    """Class describing Ecobee number entities."""


VENTILATOR_NUMBERS = (
    EcobeeNumberEntityDescription(
        key="home",
        mode="home",
        ecobee_setting_key="ventilatorMinOnTimeHome",
        set_fn=lambda data, id, min_time: data.ecobee.set_ventilator_min_on_time_home(
            id, min_time
        ),
    ),
    EcobeeNumberEntityDescription(
        key="away",
        mode="away",
        ecobee_setting_key="ventilatorMinOnTimeAway",
        set_fn=lambda data, id, min_time: data.ecobee.set_ventilator_min_on_time_away(
            id, min_time
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ecobee thermostat number entity."""
    data = hass.data[DOMAIN]
    entities = []
    _LOGGER.debug("Adding min time ventilators numbers (if present)")
    for index, thermostat in enumerate(data.ecobee.thermostats):
        if thermostat["settings"]["ventilatorType"] == "none":
            continue
        _LOGGER.debug("Adding %s's ventilator min times number", thermostat["name"])
        for numbers in VENTILATOR_NUMBERS:
            entities.append(EcobeeVentilatorMinTime(data, index, numbers))

    async_add_entities(entities, True)


class EcobeeVentilatorMinTime(EcobeeBaseEntity, NumberEntity):
    """A number class, representing min time  for an ecobee thermostat with ventilator attached."""

    _attr_native_min_value = 0
    _attr_native_max_value = 60
    _attr_native_step = 5
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_has_entity_name = True

    def __init__(self, data, thermostat_index, description):
        """Initialize ecobee ventilator platform."""
        super().__init__(data.ecobee.get_thermostat(thermostat_index))

        self.data = data
        self.thermostat_index = thermostat_index
        self.ecobee_setting_key = description.ecobee_setting_key
        self.set_fn = description.set_fn
        self._attr_name = f"Ventilator min time {description.mode}"
        self._attr_unique_id = (
            f'{self.thermostat["identifier"]}_ventilator_{description.mode}'
        )
        self._attr_native_value = self.thermostat["settings"][
            description.ecobee_setting_key
        ]

    async def async_update(self) -> None:
        """Get the latest state from the thermostat."""
        await self.data.update()
        self.thermostat = self.data.ecobee.get_thermostat(self.thermostat_index)
        self._attr_native_value = self.thermostat["settings"][self.ecobee_setting_key]

    def set_native_value(self, value: float) -> None:
        """Set new ventilator Min On Time value."""
        self.set_fn(self.data, self.thermostat_index, int(value))
