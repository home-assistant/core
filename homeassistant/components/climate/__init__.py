"""Provides functionality to interact with climate devices."""
from datetime import timedelta
import functools as ft
import logging
from typing import Any, Awaitable, Dict, Optional, List

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_TEMPERATURE, PRECISION_TENTHS, PRECISION_WHOLE,
    TEMP_CELSIUS, STATE_ON, STATE_OFF)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import (
    ServiceDataType, HomeAssistantType, ConfigType)
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA_BASE
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.temperature import display_temp as show_temp
from homeassistant.util.temperature import convert as convert_temperature

from .const import (
    ATTR_AUX_HEAT, ATTR_CURRENT_HUMIDITY, ATTR_CURRENT_HVAC,
    ATTR_CURRENT_TEMPERATURE, ATTR_FAN_LIST, ATTR_FAN_MODE, ATTR_HUMIDITY,
    ATTR_HVAC_MODE, ATTR_HVAC_MODES, ATTR_MAX_HUMIDITY, ATTR_MAX_TEMP,
    ATTR_MIN_HUMIDITY, ATTR_MIN_TEMP, ATTR_PRESET_LIST, ATTR_PRESET_MODE,
    ATTR_SWING_LIST, ATTR_SWING_MODE, ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW, ATTR_TARGET_TEMP_STEP, DOMAIN, HVAC_MODES,
    SERVICE_SET_AUX_HEAT, SERVICE_SET_FAN_MODE, SERVICE_SET_PRESET_MODE,
    SERVICE_SET_HUMIDITY, SERVICE_SET_HVAC_MODE, SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE, SUPPORT_AUX_HEAT, SUPPORT_CURRENT_HVAC,
    SUPPORT_FAN_MODE, SUPPORT_PRESET_MODE, SUPPORT_SWING_MODE,
    SUPPORT_TARGET_HUMIDITY, SUPPORT_TARGET_HUMIDITY_HIGH,
    SUPPORT_TARGET_HUMIDITY_LOW, SUPPORT_TARGET_TEMPERATURE_HIGH,
    SUPPORT_TARGET_TEMPERATURE_LOW)
from .reproduce_state import async_reproduce_states  # noqa

DEFAULT_MIN_TEMP = 7
DEFAULT_MAX_TEMP = 35
DEFAULT_MIN_HUMITIDY = 30
DEFAULT_MAX_HUMIDITY = 99

ENTITY_ID_FORMAT = DOMAIN + '.{}'
SCAN_INTERVAL = timedelta(seconds=60)

CONVERTIBLE_ATTRIBUTE = [
    ATTR_TEMPERATURE,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TARGET_TEMP_HIGH,
]

_LOGGER = logging.getLogger(__name__)

SET_AUX_HEAT_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids,
    vol.Required(ATTR_AUX_HEAT): cv.boolean,
})
SET_TEMPERATURE_SCHEMA = vol.Schema(vol.All(
    cv.has_at_least_one_key(
        ATTR_TEMPERATURE, ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW),
    {
        vol.Exclusive(ATTR_TEMPERATURE, 'temperature'): vol.Coerce(float),
        vol.Inclusive(ATTR_TARGET_TEMP_HIGH, 'temperature'): vol.Coerce(float),
        vol.Inclusive(ATTR_TARGET_TEMP_LOW, 'temperature'): vol.Coerce(float),
        vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids,
        vol.Optional(ATTR_HVAC_MODE): vol.In(HVAC_MODES),
    }
))
SET_FAN_MODE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids,
    vol.Required(ATTR_FAN_MODE): cv.string,
})
SET_PRESET_MODE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids,
    vol.Required(ATTR_PRESET_MODE): cv.string,
})
SET_HVAC_MODE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids,
    vol.Required(ATTR_HVAC_MODE): vol.In(HVAC_MODES),
})
SET_HUMIDITY_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids,
    vol.Required(ATTR_HUMIDITY): vol.Coerce(float),
})
SET_SWING_MODE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids,
    vol.Required(ATTR_SWING_MODE): cv.string,
})


async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Set up climate devices."""
    component = hass.data[DOMAIN] = \
        EntityComponent(_LOGGER, DOMAIN, hass, SCAN_INTERVAL)
    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_SET_HVAC_MODE, SET_HVAC_MODE_SCHEMA,
        'async_set_hvac_mode'
    )
    component.async_register_entity_service(
        SERVICE_SET_PRESET_MODE, SET_PRESET_MODE_SCHEMA,
        'async_set_preset_mode'
    )
    component.async_register_entity_service(
        SERVICE_SET_AUX_HEAT, SET_AUX_HEAT_SCHEMA,
        async_service_aux_heat
    )
    component.async_register_entity_service(
        SERVICE_SET_TEMPERATURE, SET_TEMPERATURE_SCHEMA,
        async_service_temperature_set
    )
    component.async_register_entity_service(
        SERVICE_SET_HUMIDITY, SET_HUMIDITY_SCHEMA,
        'async_set_humidity'
    )
    component.async_register_entity_service(
        SERVICE_SET_FAN_MODE, SET_FAN_MODE_SCHEMA,
        'async_set_fan_mode'
    )
    component.async_register_entity_service(
        SERVICE_SET_SWING_MODE, SET_SWING_MODE_SCHEMA,
        'async_set_swing_mode'
    )

    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


class ClimateDevice(Entity):
    """Representation of a climate device."""

    @property
    def state(self) -> str:
        """Return the current state."""
        return self.hvac_state

    @property
    def precision(self) -> float:
        """Return the precision of the system."""
        if self.hass.config.units.temperature_unit == TEMP_CELSIUS:
            return PRECISION_TENTHS
        return PRECISION_WHOLE

    @property
    def state_attributes(self) -> Dict[str, Any]:
        """Return the optional state attributes."""
        supported_features = self.supported_features
        data = {
            ATTR_HVAC_MODES: self.hvac_modes,
            ATTR_CURRENT_TEMPERATURE: show_temp(
                self.hass, self.current_temperature, self.temperature_unit,
                self.precision),
            ATTR_MIN_TEMP: show_temp(
                self.hass, self.min_temp, self.temperature_unit,
                self.precision),
            ATTR_MAX_TEMP: show_temp(
                self.hass, self.max_temp, self.temperature_unit,
                self.precision),
            ATTR_TEMPERATURE: show_temp(
                self.hass, self.target_temperature, self.temperature_unit,
                self.precision),
        }

        if self.target_temperature_step:
            data[ATTR_TARGET_TEMP_STEP] = self.target_temperature_step

        if supported_features & SUPPORT_TARGET_TEMPERATURE_HIGH:
            data[ATTR_TARGET_TEMP_HIGH] = show_temp(
                self.hass, self.target_temperature_high, self.temperature_unit,
                self.precision)

        if supported_features & SUPPORT_TARGET_TEMPERATURE_LOW:
            data[ATTR_TARGET_TEMP_LOW] = show_temp(
                self.hass, self.target_temperature_low, self.temperature_unit,
                self.precision)

        if self.current_humidity is not None:
            data[ATTR_CURRENT_HUMIDITY] = self.current_humidity

        if supported_features & SUPPORT_TARGET_HUMIDITY:
            data[ATTR_HUMIDITY] = self.target_humidity

            if supported_features & SUPPORT_TARGET_HUMIDITY_LOW:
                data[ATTR_MIN_HUMIDITY] = self.min_humidity

            if supported_features & SUPPORT_TARGET_HUMIDITY_HIGH:
                data[ATTR_MAX_HUMIDITY] = self.max_humidity

        if supported_features & SUPPORT_FAN_MODE:
            data[ATTR_FAN_MODE] = self.fan_mode
            if self.fan_list:
                data[ATTR_FAN_LIST] = self.fan_list

        if supported_features & SUPPORT_CURRENT_HVAC:
            data[ATTR_CURRENT_HVAC] = self.current_hvac

        if supported_features & SUPPORT_PRESET_MODE:
            data[ATTR_PRESET_MODE] = self.preset_mode
            if self.preset_list:
                data[ATTR_PRESET_LIST] = self.preset_list

        if supported_features & SUPPORT_SWING_MODE:
            data[ATTR_SWING_MODE] = self.swing_mode
            if self.swing_list:
                data[ATTR_SWING_LIST] = self.swing_list

        if supported_features & SUPPORT_AUX_HEAT:
            data[ATTR_AUX_HEAT] = STATE_ON if self.is_aux_heat else STATE_OFF

        return data

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        raise NotImplementedError()

    @property
    def current_humidity(self) -> Optional[int]:
        """Return the current humidity."""
        return None

    @property
    def target_humidity(self) -> Optional[int]:
        """Return the humidity we try to reach."""
        return None

    @property
    def hvac_state(self) -> str:
        """Return hvac operation ie. heat, cool mode

        Need to be one of HVAC_MODE_*.
        """
        raise NotImplementedError()

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        raise NotImplementedError()

    @property
    def current_hvac(self) -> Optional[str]:
        """Return the current running hvac operation if supported.

        Need to be one of CURRENT_HVAC_*.
        """
        return None

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        return None

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the temperature we try to reach."""
        return None

    @property
    def target_temperature_step(self) -> Optional[float]:
        """Return the supported step of target temperature."""
        return None

    @property
    def target_temperature_high(self) -> Optional[float]:
        """Return the highbound target temperature we try to reach."""
        return None

    @property
    def target_temperature_low(self) -> Optional[float]:
        """Return the lowbound target temperature we try to reach."""
        return None

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode, e.g., home, away, temp."""
        return None

    @property
    def preset_list(self) -> Optional[List[str]]:
        """Return a list of available preset modes."""
        return None

    @property
    def is_aux_heat(self) -> Optional[str]:
        """Return true if aux heater."""
        return None

    @property
    def fan_mode(self) -> Optional[str]:
        """Return the fan setting."""
        return None

    @property
    def fan_list(self) -> Optional[List[str]]:
        """Return the list of available fan modes."""
        return None

    @property
    def swing_mode(self) -> Optional[str]:
        """Return the fan setting."""
        return None

    @property
    def swing_list(self) -> Optional[List[str]]:
        """Return the list of available swing modes."""
        return None

    def set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        raise NotImplementedError()

    def async_set_temperature(self, **kwargs) -> Awaitable[None]:
        """Set new target temperature.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(
            ft.partial(self.set_temperature, **kwargs))

    def set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        raise NotImplementedError()

    def async_set_humidity(self, humidity: int) -> Awaitable[None]:
        """Set new target humidity.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.set_humidity, humidity)

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        raise NotImplementedError()

    def async_set_fan_mode(self, fan_mode: str) -> Awaitable[None]:
        """Set new target fan mode.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.set_fan_mode, fan_mode)

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        raise NotImplementedError()

    def async_set_hvac_mode(self, hvac_mode: str) -> Awaitable[None]:
        """Set new target hvac mode.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.set_hvac_mode, hvac_mode)

    def set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        raise NotImplementedError()

    def async_set_swing_mode(self, swing_mode: str) -> Awaitable[None]:
        """Set new target swing operation.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.set_swing_mode, swing_mode)

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        raise NotImplementedError()

    def async_set_preset_mode(self, preset_mode: str) -> Awaitable[None]:
        """Set new preset mode.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.set_preset_mode, preset_mode)

    def turn_aux_heat_on(self) -> None:
        """Turn auxiliary heater on."""
        raise NotImplementedError()

    def async_turn_aux_heat_on(self) -> Awaitable[None]:
        """Turn auxiliary heater on.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.turn_aux_heat_on)

    def turn_aux_heat_off(self) -> None:
        """Turn auxiliary heater off."""
        raise NotImplementedError()

    def async_turn_aux_heat_off(self) -> Awaitable[None]:
        """Turn auxiliary heater off.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.turn_aux_heat_off)

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        raise NotImplementedError()

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return convert_temperature(DEFAULT_MIN_TEMP, TEMP_CELSIUS,
                                   self.temperature_unit)

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return convert_temperature(DEFAULT_MAX_TEMP, TEMP_CELSIUS,
                                   self.temperature_unit)

    @property
    def min_humidity(self) -> int:
        """Return the minimum humidity."""
        return DEFAULT_MIN_HUMITIDY

    @property
    def max_humidity(self) -> int:
        """Return the maximum humidity."""
        return DEFAULT_MAX_HUMIDITY


async def async_service_aux_heat(entity, service: ServiceDataType) -> None:
    """Handle aux heat service."""
    if service.data[ATTR_AUX_HEAT]:
        await entity.async_turn_aux_heat_on()
    else:
        await entity.async_turn_aux_heat_off()


async def async_service_temperature_set(
        entity, service: ServiceDataType
) -> None:
    """Handle set temperature service."""
    hass = entity.hass
    kwargs = {}

    for value, temp in service.data.items():
        if value in CONVERTIBLE_ATTRIBUTE:
            kwargs[value] = convert_temperature(
                temp,
                hass.config.units.temperature_unit,
                entity.temperature_unit
            )
        else:
            kwargs[value] = temp

    await entity.async_set_temperature(**kwargs)
