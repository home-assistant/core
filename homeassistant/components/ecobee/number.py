"""Support for using number with ecobee thermostats."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EcobeeData
from .const import DOMAIN
from .entity import EcobeeBaseEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class EcobeeNumberEntityDescription(NumberEntityDescription):
    """Class describing Ecobee number entities."""

    ecobee_setting_key: str
    set_fn: Callable[[EcobeeData, int, int], Awaitable]


VENTILATOR_NUMBERS = (
    EcobeeNumberEntityDescription(
        key="home",
        translation_key="ventilator_min_type_home",
        ecobee_setting_key="ventilatorMinOnTimeHome",
        set_fn=lambda data, id, min_time: data.ecobee.set_ventilator_min_on_time_home(
            id, min_time
        ),
    ),
    EcobeeNumberEntityDescription(
        key="away",
        translation_key="ventilator_min_type_away",
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
    data: EcobeeData = hass.data[DOMAIN]

    assert data is not None

    entities: list[NumberEntity] = [
        EcobeeVentilatorMinTime(data, index, numbers)
        for index, thermostat in enumerate(data.ecobee.thermostats)
        if thermostat["settings"]["ventilatorType"] != "none"
        for numbers in VENTILATOR_NUMBERS
    ]

    _LOGGER.debug("Adding compressor min temp number (if present)")
    entities.extend(
        (
            EcobeeCompressorMinTemp(data, index)
            for index, thermostat in enumerate(data.ecobee.thermostats)
            if thermostat["settings"]["hasHeatPump"]
        )
    )

    async_add_entities(entities, True)


class EcobeeVentilatorMinTime(EcobeeBaseEntity, NumberEntity):
    """A number class, representing min time for an ecobee thermostat with ventilator attached."""

    entity_description: EcobeeNumberEntityDescription

    _attr_native_min_value = 0
    _attr_native_max_value = 60
    _attr_native_step = 5
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_has_entity_name = True

    def __init__(
        self,
        data: EcobeeData,
        thermostat_index: int,
        description: EcobeeNumberEntityDescription,
    ) -> None:
        """Initialize ecobee ventilator platform."""
        super().__init__(data, thermostat_index)
        self.entity_description = description
        self._attr_unique_id = f"{self.base_unique_id}_ventilator_{description.key}"
        self.update_without_throttle = False

    async def async_update(self) -> None:
        """Get the latest state from the thermostat."""
        if self.update_without_throttle:
            await self.data.update(no_throttle=True)
            self.update_without_throttle = False
        else:
            await self.data.update()
        self._attr_native_value = self.thermostat["settings"][
            self.entity_description.ecobee_setting_key
        ]

    def set_native_value(self, value: float) -> None:
        """Set new ventilator Min On Time value."""
        self.entity_description.set_fn(self.data, self.thermostat_index, int(value))
        self.update_without_throttle = True


class EcobeeCompressorMinTemp(EcobeeBaseEntity, NumberEntity):
    """Minimum outdoor temperature at which the compressor will operate.

    This applies more to air source heat pumps than geothermal. This serves as a safety
         feature (compressors have a minimum operating temperature) as well as
        providing the ability to choose fuel in a dual-fuel system (i.e. choose between
        electrical heat pump and fossil auxiliary heat depending on Time of Use, Solar,
        etc.).
        Note that python-ecobee-api refers to this as Aux Cutover Threshold, but Ecobee
        uses Compressor Protection Min Temp.
    """

    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_has_entity_name = True
    _attr_icon = "mdi:thermometer-off"
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = -25
    _attr_native_max_value = 66
    _attr_native_step = 5
    _attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
    _attr_translation_key = "compressor_protection_min_temp"

    def __init__(
        self,
        data: EcobeeData,
        thermostat_index: int,
    ) -> None:
        """Initialize ecobee compressor min temperature."""
        super().__init__(data, thermostat_index)
        self._attr_unique_id = f"{self.base_unique_id}_compressor_protection_min_temp"
        self.update_without_throttle = False

    async def async_update(self) -> None:
        """Get the latest state from the thermostat."""
        if self.update_without_throttle:
            await self.data.update(no_throttle=True)
            self.update_without_throttle = False
        else:
            await self.data.update()

        self._attr_native_value = (
            (self.thermostat["settings"]["compressorProtectionMinTemp"]) / 10
        )

    def set_native_value(self, value: float) -> None:
        """Set new compressor minimum temperature."""
        self.data.ecobee.set_aux_cutover_threshold(self.thermostat_index, value)
        self.update_without_throttle = True
