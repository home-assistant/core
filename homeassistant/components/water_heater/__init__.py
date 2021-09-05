"""Support for water heater devices."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import functools as ft
import logging
from typing import final

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.temperature import display_temp as show_temp
from homeassistant.util.temperature import convert as convert_temperature

# mypy: allow-untyped-defs, no-check-untyped-defs

DEFAULT_MIN_TEMP = 110
DEFAULT_MAX_TEMP = 140

DOMAIN = "water_heater"

ENTITY_ID_FORMAT = DOMAIN + ".{}"
SCAN_INTERVAL = timedelta(seconds=60)

SERVICE_SET_AWAY_MODE = "set_away_mode"
SERVICE_SET_TEMPERATURE = "set_temperature"
SERVICE_SET_OPERATION_MODE = "set_operation_mode"

STATE_ECO = "eco"
STATE_ELECTRIC = "electric"
STATE_PERFORMANCE = "performance"
STATE_HIGH_DEMAND = "high_demand"
STATE_HEAT_PUMP = "heat_pump"
STATE_GAS = "gas"

SUPPORT_TARGET_TEMPERATURE = 1
SUPPORT_OPERATION_MODE = 2
SUPPORT_AWAY_MODE = 4

ATTR_MAX_TEMP = "max_temp"
ATTR_MIN_TEMP = "min_temp"
ATTR_AWAY_MODE = "away_mode"
ATTR_OPERATION_MODE = "operation_mode"
ATTR_OPERATION_LIST = "operation_list"
ATTR_TARGET_TEMP_HIGH = "target_temp_high"
ATTR_TARGET_TEMP_LOW = "target_temp_low"
ATTR_CURRENT_TEMPERATURE = "current_temperature"

CONVERTIBLE_ATTRIBUTE = [ATTR_TEMPERATURE]

_LOGGER = logging.getLogger(__name__)

ON_OFF_SERVICE_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids})

SET_AWAY_MODE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids,
        vol.Required(ATTR_AWAY_MODE): cv.boolean,
    }
)
SET_TEMPERATURE_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required(ATTR_TEMPERATURE, "temperature"): vol.Coerce(float),
            vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids,
            vol.Optional(ATTR_OPERATION_MODE): cv.string,
        }
    )
)
SET_OPERATION_MODE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids,
        vol.Required(ATTR_OPERATION_MODE): cv.string,
    }
)


async def async_setup(hass, config):
    """Set up water_heater devices."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_SET_AWAY_MODE, SET_AWAY_MODE_SCHEMA, async_service_away_mode
    )
    component.async_register_entity_service(
        SERVICE_SET_TEMPERATURE, SET_TEMPERATURE_SCHEMA, async_service_temperature_set
    )
    component.async_register_entity_service(
        SERVICE_SET_OPERATION_MODE,
        SET_OPERATION_MODE_SCHEMA,
        "async_set_operation_mode",
    )
    component.async_register_entity_service(
        SERVICE_TURN_OFF, ON_OFF_SERVICE_SCHEMA, "async_turn_off"
    )
    component.async_register_entity_service(
        SERVICE_TURN_ON, ON_OFF_SERVICE_SCHEMA, "async_turn_on"
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


@dataclass
class WaterHeaterEntityEntityDescription(EntityDescription):
    """A class that describes water heater entities."""


class WaterHeaterEntity(Entity):
    """Base class for water heater entities."""

    entity_description: WaterHeaterEntityEntityDescription
    _attr_current_operation: str | None = None
    _attr_current_temperature: float | None = None
    _attr_is_away_mode_on: bool | None = None
    _attr_max_temp: float
    _attr_min_temp: float
    _attr_operation_list: list[str] | None = None
    _attr_precision: float
    _attr_state: None = None
    _attr_supported_features: int
    _attr_target_temperature_high: float | None = None
    _attr_target_temperature_low: float | None = None
    _attr_target_temperature: float | None = None
    _attr_temperature_unit: str

    @final
    @property
    def state(self) -> str | None:
        """Return the current state."""
        return self.current_operation

    @property
    def precision(self) -> float:
        """Return the precision of the system."""
        if hasattr(self, "_attr_precision"):
            return self._attr_precision
        if self.hass.config.units.temperature_unit == TEMP_CELSIUS:
            return PRECISION_TENTHS
        return PRECISION_WHOLE

    @property
    def capability_attributes(self):
        """Return capability attributes."""
        supported_features = self.supported_features or 0

        data = {
            ATTR_MIN_TEMP: show_temp(
                self.hass, self.min_temp, self.temperature_unit, self.precision
            ),
            ATTR_MAX_TEMP: show_temp(
                self.hass, self.max_temp, self.temperature_unit, self.precision
            ),
        }

        if supported_features & SUPPORT_OPERATION_MODE:
            data[ATTR_OPERATION_LIST] = self.operation_list

        return data

    @final
    @property
    def state_attributes(self):
        """Return the optional state attributes."""
        data = {
            ATTR_CURRENT_TEMPERATURE: show_temp(
                self.hass,
                self.current_temperature,
                self.temperature_unit,
                self.precision,
            ),
            ATTR_TEMPERATURE: show_temp(
                self.hass,
                self.target_temperature,
                self.temperature_unit,
                self.precision,
            ),
            ATTR_TARGET_TEMP_HIGH: show_temp(
                self.hass,
                self.target_temperature_high,
                self.temperature_unit,
                self.precision,
            ),
            ATTR_TARGET_TEMP_LOW: show_temp(
                self.hass,
                self.target_temperature_low,
                self.temperature_unit,
                self.precision,
            ),
        }

        supported_features = self.supported_features

        if supported_features & SUPPORT_OPERATION_MODE:
            data[ATTR_OPERATION_MODE] = self.current_operation

        if supported_features & SUPPORT_AWAY_MODE:
            is_away = self.is_away_mode_on
            data[ATTR_AWAY_MODE] = STATE_ON if is_away else STATE_OFF

        return data

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        return self._attr_temperature_unit

    @property
    def current_operation(self) -> str | None:
        """Return current operation ie. eco, electric, performance, ..."""
        return self._attr_current_operation

    @property
    def operation_list(self) -> list[str] | None:
        """Return the list of available operation modes."""
        return self._attr_operation_list

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._attr_current_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._attr_target_temperature

    @property
    def target_temperature_high(self) -> float | None:
        """Return the highbound target temperature we try to reach."""
        return self._attr_target_temperature_high

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach."""
        return self._attr_target_temperature_low

    @property
    def is_away_mode_on(self) -> bool | None:
        """Return true if away mode is on."""
        return self._attr_is_away_mode_on

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        raise NotImplementedError()

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        await self.hass.async_add_executor_job(
            ft.partial(self.set_temperature, **kwargs)
        )

    def set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        raise NotImplementedError()

    async def async_set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        await self.hass.async_add_executor_job(self.set_operation_mode, operation_mode)

    def turn_away_mode_on(self):
        """Turn away mode on."""
        raise NotImplementedError()

    async def async_turn_away_mode_on(self):
        """Turn away mode on."""
        await self.hass.async_add_executor_job(self.turn_away_mode_on)

    def turn_away_mode_off(self):
        """Turn away mode off."""
        raise NotImplementedError()

    async def async_turn_away_mode_off(self):
        """Turn away mode off."""
        await self.hass.async_add_executor_job(self.turn_away_mode_off)

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        if hasattr(self, "_attr_min_temp"):
            return self._attr_min_temp
        return convert_temperature(
            DEFAULT_MIN_TEMP, TEMP_FAHRENHEIT, self.temperature_unit
        )

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        if hasattr(self, "_attr_max_temp"):
            return self._attr_max_temp
        return convert_temperature(
            DEFAULT_MAX_TEMP, TEMP_FAHRENHEIT, self.temperature_unit
        )


async def async_service_away_mode(entity, service):
    """Handle away mode service."""
    if service.data[ATTR_AWAY_MODE]:
        await entity.async_turn_away_mode_on()
    else:
        await entity.async_turn_away_mode_off()


async def async_service_temperature_set(entity, service):
    """Handle set temperature service."""
    hass = entity.hass
    kwargs = {}

    for value, temp in service.data.items():
        if value in CONVERTIBLE_ATTRIBUTE:
            kwargs[value] = convert_temperature(
                temp, hass.config.units.temperature_unit, entity.temperature_unit
            )
        else:
            kwargs[value] = temp

    await entity.async_set_temperature(**kwargs)


class WaterHeaterDevice(WaterHeaterEntity):
    """Representation of a water heater (for backwards compatibility)."""

    def __init_subclass__(cls, **kwargs):
        """Print deprecation warning."""
        super().__init_subclass__(**kwargs)
        _LOGGER.warning(
            "WaterHeaterDevice is deprecated, modify %s to extend WaterHeaterEntity",
            cls.__name__,
        )
