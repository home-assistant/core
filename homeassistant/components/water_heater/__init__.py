"""Support for water heater devices."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from enum import IntEnum
import functools as ft
import logging
from typing import Any, final

import voluptuous as vol

from homeassistant.backports.enum import StrEnum
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.temperature import display_temp as show_temp
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.unit_conversion import TemperatureConverter

DEFAULT_MIN_TEMP = 110
DEFAULT_MAX_TEMP = 140

DOMAIN = "water_heater"

ENTITY_ID_FORMAT = DOMAIN + ".{}"
SCAN_INTERVAL = timedelta(seconds=60)

SERVICE_SET_TEMPERATURE = "set_temperature"
SERVICE_SET_OPERATION_MODE = "set_operation_mode"
SERVICE_SET_PRESET_MODE = "set_preset_mode"

STATE_ECO = "eco"
STATE_ELECTRIC = "electric"
STATE_PERFORMANCE = "performance"
STATE_HIGH_DEMAND = "high_demand"
STATE_HEAT_PUMP = "heat_pump"
STATE_GAS = "gas"


class WaterHeaterOperationMode(StrEnum):
    """Supported operation modes of a heater."""

    OFF = "off"
    ON = "on"
    LEGIONELLA_PREVENTION = "legionella_prevention"
    BOOST = "boost"
    AWAY = "away"


class WaterHeaterCurrentOperation(StrEnum):
    """Supported current operations of a heater."""

    OFF = "off"
    IDLE = "idle"
    HEATING = "heating"
    LEGIONELLA_PREVENTION = "legionella_prevention"
    BOOST = "boost"


class WaterHeaterEntityFeature(IntEnum):
    """Supported features of the fan entity."""

    TARGET_TEMPERATURE = 1
    OPERATION_MODE = 2
    PRESET_MODE = 8


ATTR_MAX_TEMP = "max_temp"
ATTR_MIN_TEMP = "min_temp"
ATTR_AWAY_MODE = "away_mode"
ATTR_OPERATION_MODE = "operation_mode"
ATTR_OPERATION_MODES = "operation_modes"
ATTR_TARGET_TEMP_HIGH = "target_temp_high"
ATTR_TARGET_TEMP_LOW = "target_temp_low"
ATTR_CURRENT_TEMPERATURE = "current_temperature"
ATTR_CURRENT_OPERATION = "current_operation"
ATTR_PRESET_MODE = "preset_mode"
ATTR_PRESET_MODES = "preset_modes"

CONVERTIBLE_ATTRIBUTE = [ATTR_TEMPERATURE, ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW]

_LOGGER = logging.getLogger(__name__)

ON_OFF_SERVICE_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids})

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

# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up water_heater devices."""
    component = hass.data[DOMAIN] = EntityComponent[WaterHeaterEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_SET_PRESET_MODE,
        {vol.Required(ATTR_PRESET_MODE): cv.string},
        "async_set_preset_mode",
        [WaterHeaterEntityFeature.PRESET_MODE],
    )
    component.async_register_entity_service(
        SERVICE_SET_TEMPERATURE,
        SET_TEMPERATURE_SCHEMA,
        async_service_temperature_set,
        [WaterHeaterEntityFeature.TARGET_TEMPERATURE],
    )
    component.async_register_entity_service(
        SERVICE_SET_OPERATION_MODE,
        SET_OPERATION_MODE_SCHEMA,
        "async_set_operation_mode",
        [WaterHeaterEntityFeature.OPERATION_MODE],
    )
    component.async_register_entity_service(
        SERVICE_TURN_OFF,
        ON_OFF_SERVICE_SCHEMA,
        "async_turn_off",
        [WaterHeaterEntityFeature.OPERATION_MODE],
    )
    component.async_register_entity_service(
        SERVICE_TURN_ON,
        ON_OFF_SERVICE_SCHEMA,
        "async_turn_on",
        [WaterHeaterEntityFeature.OPERATION_MODE],
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent[WaterHeaterEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[WaterHeaterEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


@dataclass
class WaterHeaterEntityEntityDescription(EntityDescription):
    """A class that describes water heater entities."""


class WaterHeaterEntity(Entity):
    """Base class for water heater entities."""

    entity_description: WaterHeaterEntityEntityDescription
    _attr_current_operation: WaterHeaterCurrentOperation | str | None = None
    _attr_current_temperature: float | None = None
    _attr_max_temp: float
    _attr_min_temp: float
    _attr_operation_mode: WaterHeaterOperationMode | str | None = None
    _attr_operation_modes: list[WaterHeaterOperationMode] | list[str]
    _attr_precision: float
    _attr_preset_mode: str | None
    _attr_preset_modes: list[str] | None
    _attr_state: None = None
    _attr_supported_features: int = 0
    _attr_target_temperature_high: float | None = None
    _attr_target_temperature_low: float | None = None
    _attr_target_temperature: float | None = None
    _attr_temperature_unit: str

    @final
    @property
    def state(self) -> str | None:
        """Return the current state."""
        return self.operation_mode

    @property
    def precision(self) -> float:
        """Return the precision of the system."""
        if hasattr(self, "_attr_precision"):
            return self._attr_precision
        if self.hass.config.units.temperature_unit == TEMP_CELSIUS:
            return PRECISION_TENTHS
        return PRECISION_WHOLE

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return self._attr_supported_features

    @property
    def capability_attributes(self) -> Mapping[str, Any]:
        """Return capability attributes."""
        supported_features = self.supported_features

        data: dict[str, Any] = {
            ATTR_MIN_TEMP: show_temp(
                self.hass, self.min_temp, self.temperature_unit, self.precision
            ),
            ATTR_MAX_TEMP: show_temp(
                self.hass, self.max_temp, self.temperature_unit, self.precision
            ),
        }

        if supported_features & WaterHeaterEntityFeature.OPERATION_MODE:
            data[ATTR_OPERATION_MODES] = self.operation_modes

        if supported_features & WaterHeaterEntityFeature.PRESET_MODE:
            data[ATTR_PRESET_MODES] = self.preset_modes

        return data

    @final
    @property
    def state_attributes(self) -> dict[str, Any]:
        """Return the optional state attributes."""
        data: dict[str, Any] = {
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

        data[ATTR_OPERATION_MODE] = self.operation_mode
        data[ATTR_CURRENT_OPERATION] = self.current_operation
        data[ATTR_PRESET_MODE] = self.preset_mode

        return data

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        return self._attr_temperature_unit

    @property
    def current_operation(self) -> WaterHeaterCurrentOperation | str | None:
        """Return current operation."""
        return self._attr_current_operation

    @property
    def operation_mode(self) -> WaterHeaterOperationMode | str | None:
        """Return the operation mode active."""
        return self._attr_operation_mode

    @property
    def operation_modes(self) -> list[WaterHeaterOperationMode] | list[str]:
        """Return the list of available operation modes."""
        return self._attr_operation_modes

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
    def preset_mode(self) -> str | None:
        """Return the current preset mode.

        Requires WaterHeaterEntityFeature.PRESET_MODE.
        """
        return self._attr_preset_mode

    @property
    def preset_modes(self) -> list[str] | None:
        """Return a list of available preset modes.

        Requires WaterHeaterEntityFeature.PRESET_MODE.
        """
        return self._attr_preset_modes

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        raise NotImplementedError()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        await self.hass.async_add_executor_job(
            ft.partial(self.set_temperature, **kwargs)
        )

    def set_operation_mode(self, operation_mode: WaterHeaterOperationMode) -> None:
        """Set new target operation mode."""
        raise NotImplementedError()

    async def async_set_operation_mode(
        self, operation_mode: WaterHeaterOperationMode
    ) -> None:
        """Set new target operation mode."""
        await self.hass.async_add_executor_job(self.set_operation_mode, operation_mode)

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        if turn_on := getattr(self, "turn_on"):
            await self.hass.async_add_executor_job(turn_on)
            return

        if WaterHeaterOperationMode.ON not in self.operation_modes:
            raise NotImplementedError()

        await self.async_set_operation_mode(WaterHeaterOperationMode.ON)

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        if turn_off := getattr(self, "turn_off"):
            await self.hass.async_add_executor_job(turn_off)
            return

        if WaterHeaterOperationMode.OFF not in self.operation_modes:
            raise NotImplementedError()

        await self.async_set_operation_mode(WaterHeaterOperationMode.OFF)

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        raise NotImplementedError()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self.hass.async_add_executor_job(self.set_preset_mode, preset_mode)

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        if hasattr(self, "_attr_min_temp"):
            return self._attr_min_temp
        return TemperatureConverter.convert(
            DEFAULT_MIN_TEMP, TEMP_FAHRENHEIT, self.temperature_unit
        )

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        if hasattr(self, "_attr_max_temp"):
            return self._attr_max_temp
        return TemperatureConverter.convert(
            DEFAULT_MAX_TEMP, TEMP_FAHRENHEIT, self.temperature_unit
        )


async def async_service_temperature_set(
    entity: WaterHeaterEntity, service: ServiceCall
) -> None:
    """Handle set temperature service."""
    hass = entity.hass
    kwargs = {}

    for value, temp in service.data.items():
        if value in CONVERTIBLE_ATTRIBUTE:
            kwargs[value] = TemperatureConverter.convert(
                temp, hass.config.units.temperature_unit, entity.temperature_unit
            )
        else:
            kwargs[value] = temp

    await entity.async_set_temperature(**kwargs)
