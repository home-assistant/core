"""
Provides functionality to interact with climate devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/climate/
"""
from datetime import timedelta
import logging
import functools as ft

import voluptuous as vol

from homeassistant.helpers.temperature import display_temp as show_temp
from homeassistant.util.temperature import convert as convert_temperature
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_TEMPERATURE, SERVICE_TURN_ON, SERVICE_TURN_OFF,
    STATE_ON, STATE_OFF, STATE_UNKNOWN, TEMP_CELSIUS, PRECISION_WHOLE,
    PRECISION_TENTHS)

DEFAULT_MIN_TEMP = 7
DEFAULT_MAX_TEMP = 35
DEFAULT_MIN_HUMITIDY = 30
DEFAULT_MAX_HUMIDITY = 99

DOMAIN = 'climate'

ENTITY_ID_FORMAT = DOMAIN + '.{}'
SCAN_INTERVAL = timedelta(seconds=60)

SERVICE_SET_AWAY_MODE = 'set_away_mode'
SERVICE_SET_AUX_HEAT = 'set_aux_heat'
SERVICE_SET_TEMPERATURE = 'set_temperature'
SERVICE_SET_FAN_MODE = 'set_fan_mode'
SERVICE_SET_HOLD_MODE = 'set_hold_mode'
SERVICE_SET_OPERATION_MODE = 'set_operation_mode'
SERVICE_SET_SWING_MODE = 'set_swing_mode'
SERVICE_SET_HUMIDITY = 'set_humidity'

STATE_HEAT = 'heat'
STATE_COOL = 'cool'
STATE_IDLE = 'idle'
STATE_AUTO = 'auto'
STATE_MANUAL = 'manual'
STATE_DRY = 'dry'
STATE_FAN_ONLY = 'fan_only'
STATE_ECO = 'eco'

SUPPORT_TARGET_TEMPERATURE = 1
SUPPORT_TARGET_TEMPERATURE_HIGH = 2
SUPPORT_TARGET_TEMPERATURE_LOW = 4
SUPPORT_TARGET_HUMIDITY = 8
SUPPORT_TARGET_HUMIDITY_HIGH = 16
SUPPORT_TARGET_HUMIDITY_LOW = 32
SUPPORT_FAN_MODE = 64
SUPPORT_OPERATION_MODE = 128
SUPPORT_HOLD_MODE = 256
SUPPORT_SWING_MODE = 512
SUPPORT_AWAY_MODE = 1024
SUPPORT_AUX_HEAT = 2048
SUPPORT_ON_OFF = 4096

ATTR_CURRENT_TEMPERATURE = 'current_temperature'
ATTR_MAX_TEMP = 'max_temp'
ATTR_MIN_TEMP = 'min_temp'
ATTR_TARGET_TEMP_HIGH = 'target_temp_high'
ATTR_TARGET_TEMP_LOW = 'target_temp_low'
ATTR_TARGET_TEMP_STEP = 'target_temp_step'
ATTR_AWAY_MODE = 'away_mode'
ATTR_AUX_HEAT = 'aux_heat'
ATTR_FAN_MODE = 'fan_mode'
ATTR_FAN_LIST = 'fan_list'
ATTR_CURRENT_HUMIDITY = 'current_humidity'
ATTR_HUMIDITY = 'humidity'
ATTR_MAX_HUMIDITY = 'max_humidity'
ATTR_MIN_HUMIDITY = 'min_humidity'
ATTR_HOLD_MODE = 'hold_mode'
ATTR_OPERATION_MODE = 'operation_mode'
ATTR_OPERATION_LIST = 'operation_list'
ATTR_SWING_MODE = 'swing_mode'
ATTR_SWING_LIST = 'swing_list'

CONVERTIBLE_ATTRIBUTE = [
    ATTR_TEMPERATURE,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TARGET_TEMP_HIGH,
]

_LOGGER = logging.getLogger(__name__)

ON_OFF_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})

SET_AWAY_MODE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_AWAY_MODE): cv.boolean,
})
SET_AUX_HEAT_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_AUX_HEAT): cv.boolean,
})
SET_TEMPERATURE_SCHEMA = vol.Schema(vol.All(
    cv.has_at_least_one_key(
        ATTR_TEMPERATURE, ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW),
    {
        vol.Exclusive(ATTR_TEMPERATURE, 'temperature'): vol.Coerce(float),
        vol.Inclusive(ATTR_TARGET_TEMP_HIGH, 'temperature'): vol.Coerce(float),
        vol.Inclusive(ATTR_TARGET_TEMP_LOW, 'temperature'): vol.Coerce(float),
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Optional(ATTR_OPERATION_MODE): cv.string,
    }
))
SET_FAN_MODE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_FAN_MODE): cv.string,
})
SET_HOLD_MODE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_HOLD_MODE): cv.string,
})
SET_OPERATION_MODE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_OPERATION_MODE): cv.string,
})
SET_HUMIDITY_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_HUMIDITY): vol.Coerce(float),
})
SET_SWING_MODE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_SWING_MODE): cv.string,
})


async def async_setup(hass, config):
    """Set up climate devices."""
    component = hass.data[DOMAIN] = \
        EntityComponent(_LOGGER, DOMAIN, hass, SCAN_INTERVAL)
    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_SET_AWAY_MODE, SET_AWAY_MODE_SCHEMA,
        async_service_away_mode
    )
    component.async_register_entity_service(
        SERVICE_SET_HOLD_MODE, SET_HOLD_MODE_SCHEMA,
        'async_set_hold_mode'
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
        SERVICE_SET_OPERATION_MODE, SET_OPERATION_MODE_SCHEMA,
        'async_set_operation_mode'
    )
    component.async_register_entity_service(
        SERVICE_SET_SWING_MODE, SET_SWING_MODE_SCHEMA,
        'async_set_swing_mode'
    )
    component.async_register_entity_service(
        SERVICE_TURN_OFF, ON_OFF_SERVICE_SCHEMA,
        'async_turn_off'
    )
    component.async_register_entity_service(
        SERVICE_TURN_ON, ON_OFF_SERVICE_SCHEMA,
        'async_turn_on'
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
    def state(self):
        """Return the current state."""
        if self.is_on is False:
            return STATE_OFF
        if self.current_operation:
            return self.current_operation
        if self.is_on:
            return STATE_ON
        return STATE_UNKNOWN

    @property
    def precision(self):
        """Return the precision of the system."""
        if self.hass.config.units.temperature_unit == TEMP_CELSIUS:
            return PRECISION_TENTHS
        return PRECISION_WHOLE

    @property
    def state_attributes(self):
        """Return the optional state attributes."""
        data = {
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

        supported_features = self.supported_features
        if self.target_temperature_step is not None:
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
            data[ATTR_FAN_MODE] = self.current_fan_mode
            if self.fan_list:
                data[ATTR_FAN_LIST] = self.fan_list

        if supported_features & SUPPORT_OPERATION_MODE:
            data[ATTR_OPERATION_MODE] = self.current_operation
            if self.operation_list:
                data[ATTR_OPERATION_LIST] = self.operation_list

        if supported_features & SUPPORT_HOLD_MODE:
            data[ATTR_HOLD_MODE] = self.current_hold_mode

        if supported_features & SUPPORT_SWING_MODE:
            data[ATTR_SWING_MODE] = self.current_swing_mode
            if self.swing_list:
                data[ATTR_SWING_LIST] = self.swing_list

        if supported_features & SUPPORT_AWAY_MODE:
            is_away = self.is_away_mode_on
            data[ATTR_AWAY_MODE] = STATE_ON if is_away else STATE_OFF

        if supported_features & SUPPORT_AUX_HEAT:
            is_aux_heat = self.is_aux_heat_on
            data[ATTR_AUX_HEAT] = STATE_ON if is_aux_heat else STATE_OFF

        return data

    @property
    def temperature_unit(self):
        """Return the unit of measurement used by the platform."""
        raise NotImplementedError

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return None

    @property
    def target_humidity(self):
        """Return the humidity we try to reach."""
        return None

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return None

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return None

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return None

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return None

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return None

    @property
    def target_temperature_high(self):
        """Return the highbound target temperature we try to reach."""
        return None

    @property
    def target_temperature_low(self):
        """Return the lowbound target temperature we try to reach."""
        return None

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        return None

    @property
    def current_hold_mode(self):
        """Return the current hold mode, e.g., home, away, temp."""
        return None

    @property
    def is_on(self):
        """Return true if on."""
        return None

    @property
    def is_aux_heat_on(self):
        """Return true if aux heater."""
        return None

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        return None

    @property
    def fan_list(self):
        """Return the list of available fan modes."""
        return None

    @property
    def current_swing_mode(self):
        """Return the fan setting."""
        return None

    @property
    def swing_list(self):
        """Return the list of available swing modes."""
        return None

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        raise NotImplementedError()

    def async_set_temperature(self, **kwargs):
        """Set new target temperature.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(
            ft.partial(self.set_temperature, **kwargs))

    def set_humidity(self, humidity):
        """Set new target humidity."""
        raise NotImplementedError()

    def async_set_humidity(self, humidity):
        """Set new target humidity.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.set_humidity, humidity)

    def set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        raise NotImplementedError()

    def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.set_fan_mode, fan_mode)

    def set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        raise NotImplementedError()

    def async_set_operation_mode(self, operation_mode):
        """Set new target operation mode.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.set_operation_mode, operation_mode)

    def set_swing_mode(self, swing_mode):
        """Set new target swing operation."""
        raise NotImplementedError()

    def async_set_swing_mode(self, swing_mode):
        """Set new target swing operation.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.set_swing_mode, swing_mode)

    def turn_away_mode_on(self):
        """Turn away mode on."""
        raise NotImplementedError()

    def async_turn_away_mode_on(self):
        """Turn away mode on.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.turn_away_mode_on)

    def turn_away_mode_off(self):
        """Turn away mode off."""
        raise NotImplementedError()

    def async_turn_away_mode_off(self):
        """Turn away mode off.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.turn_away_mode_off)

    def set_hold_mode(self, hold_mode):
        """Set new target hold mode."""
        raise NotImplementedError()

    def async_set_hold_mode(self, hold_mode):
        """Set new target hold mode.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.set_hold_mode, hold_mode)

    def turn_aux_heat_on(self):
        """Turn auxiliary heater on."""
        raise NotImplementedError()

    def async_turn_aux_heat_on(self):
        """Turn auxiliary heater on.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.turn_aux_heat_on)

    def turn_aux_heat_off(self):
        """Turn auxiliary heater off."""
        raise NotImplementedError()

    def async_turn_aux_heat_off(self):
        """Turn auxiliary heater off.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.turn_aux_heat_off)

    def turn_on(self):
        """Turn device on."""
        raise NotImplementedError()

    def async_turn_on(self):
        """Turn device on.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.turn_on)

    def turn_off(self):
        """Turn device off."""
        raise NotImplementedError()

    def async_turn_off(self):
        """Turn device off.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.turn_off)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        raise NotImplementedError()

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return convert_temperature(DEFAULT_MIN_TEMP, TEMP_CELSIUS,
                                   self.temperature_unit)

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return convert_temperature(DEFAULT_MAX_TEMP, TEMP_CELSIUS,
                                   self.temperature_unit)

    @property
    def min_humidity(self):
        """Return the minimum humidity."""
        return DEFAULT_MIN_HUMITIDY

    @property
    def max_humidity(self):
        """Return the maximum humidity."""
        return DEFAULT_MAX_HUMIDITY


async def async_service_away_mode(entity, service):
    """Handle away mode service."""
    if service.data[ATTR_AWAY_MODE]:
        await entity.async_turn_away_mode_on()
    else:
        await entity.async_turn_away_mode_off()


async def async_service_aux_heat(entity, service):
    """Handle aux heat service."""
    if service.data[ATTR_AUX_HEAT]:
        await entity.async_turn_aux_heat_on()
    else:
        await entity.async_turn_aux_heat_off()


async def async_service_temperature_set(entity, service):
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
