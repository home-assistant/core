"""
Provides functionality to interact with climate devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/climate/
"""
import asyncio
from datetime import timedelta
import logging
import os
import functools as ft

import voluptuous as vol

from homeassistant.config import load_yaml_config_file
from homeassistant.loader import bind_hass
from homeassistant.helpers.temperature import display_temp as show_temp
from homeassistant.util.temperature import convert as convert_temperature
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_TEMPERATURE, STATE_ON, STATE_OFF, STATE_UNKNOWN,
    TEMP_CELSIUS, PRECISION_WHOLE, PRECISION_TENTHS)

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
STATE_DRY = 'dry'
STATE_FAN_ONLY = 'fan_only'
STATE_ECO = 'eco'
STATE_ELECTRIC = 'electric'
STATE_PERFORMANCE = 'performance'
STATE_HIGH_DEMAND = 'high_demand'
STATE_HEAT_PUMP = 'heat_pump'
STATE_GAS = 'gas'

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


@bind_hass
def set_away_mode(hass, away_mode, entity_id=None):
    """Turn all or specified climate devices away mode on."""
    data = {
        ATTR_AWAY_MODE: away_mode
    }

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_AWAY_MODE, data)


@bind_hass
def set_hold_mode(hass, hold_mode, entity_id=None):
    """Set new hold mode."""
    data = {
        ATTR_HOLD_MODE: hold_mode
    }

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_HOLD_MODE, data)


@bind_hass
def set_aux_heat(hass, aux_heat, entity_id=None):
    """Turn all or specified climate devices auxiliary heater on."""
    data = {
        ATTR_AUX_HEAT: aux_heat
    }

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_AUX_HEAT, data)


@bind_hass
def set_temperature(hass, temperature=None, entity_id=None,
                    target_temp_high=None, target_temp_low=None,
                    operation_mode=None):
    """Set new target temperature."""
    kwargs = {
        key: value for key, value in [
            (ATTR_TEMPERATURE, temperature),
            (ATTR_TARGET_TEMP_HIGH, target_temp_high),
            (ATTR_TARGET_TEMP_LOW, target_temp_low),
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_OPERATION_MODE, operation_mode)
        ] if value is not None
    }
    _LOGGER.debug("set_temperature start data=%s", kwargs)
    hass.services.call(DOMAIN, SERVICE_SET_TEMPERATURE, kwargs)


@bind_hass
def set_humidity(hass, humidity, entity_id=None):
    """Set new target humidity."""
    data = {ATTR_HUMIDITY: humidity}

    if entity_id is not None:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_HUMIDITY, data)


@bind_hass
def set_fan_mode(hass, fan, entity_id=None):
    """Set all or specified climate devices fan mode on."""
    data = {ATTR_FAN_MODE: fan}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_FAN_MODE, data)


@bind_hass
def set_operation_mode(hass, operation_mode, entity_id=None):
    """Set new target operation mode."""
    data = {ATTR_OPERATION_MODE: operation_mode}

    if entity_id is not None:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_OPERATION_MODE, data)


@bind_hass
def set_swing_mode(hass, swing_mode, entity_id=None):
    """Set new target swing mode."""
    data = {ATTR_SWING_MODE: swing_mode}

    if entity_id is not None:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_SWING_MODE, data)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up climate devices."""
    component = EntityComponent(_LOGGER, DOMAIN, hass, SCAN_INTERVAL)
    yield from component.async_setup(config)

    descriptions = yield from hass.async_add_job(
        load_yaml_config_file,
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    @asyncio.coroutine
    def async_away_mode_set_service(service):
        """Set away mode on target climate devices."""
        target_climate = component.async_extract_from_service(service)

        away_mode = service.data.get(ATTR_AWAY_MODE)

        update_tasks = []
        for climate in target_climate:
            if away_mode:
                yield from climate.async_turn_away_mode_on()
            else:
                yield from climate.async_turn_away_mode_off()

            if not climate.should_poll:
                continue
            update_tasks.append(climate.async_update_ha_state(True))

        if update_tasks:
            yield from asyncio.wait(update_tasks, loop=hass.loop)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_AWAY_MODE, async_away_mode_set_service,
        descriptions.get(SERVICE_SET_AWAY_MODE),
        schema=SET_AWAY_MODE_SCHEMA)

    @asyncio.coroutine
    def async_hold_mode_set_service(service):
        """Set hold mode on target climate devices."""
        target_climate = component.async_extract_from_service(service)

        hold_mode = service.data.get(ATTR_HOLD_MODE)

        update_tasks = []
        for climate in target_climate:
            yield from climate.async_set_hold_mode(hold_mode)

            if not climate.should_poll:
                continue
            update_tasks.append(climate.async_update_ha_state(True))

        if update_tasks:
            yield from asyncio.wait(update_tasks, loop=hass.loop)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_HOLD_MODE, async_hold_mode_set_service,
        descriptions.get(SERVICE_SET_HOLD_MODE),
        schema=SET_HOLD_MODE_SCHEMA)

    @asyncio.coroutine
    def async_aux_heat_set_service(service):
        """Set auxiliary heater on target climate devices."""
        target_climate = component.async_extract_from_service(service)

        aux_heat = service.data.get(ATTR_AUX_HEAT)

        update_tasks = []
        for climate in target_climate:
            if aux_heat:
                yield from climate.async_turn_aux_heat_on()
            else:
                yield from climate.async_turn_aux_heat_off()

            if not climate.should_poll:
                continue
            update_tasks.append(climate.async_update_ha_state(True))

        if update_tasks:
            yield from asyncio.wait(update_tasks, loop=hass.loop)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_AUX_HEAT, async_aux_heat_set_service,
        descriptions.get(SERVICE_SET_AUX_HEAT),
        schema=SET_AUX_HEAT_SCHEMA)

    @asyncio.coroutine
    def async_temperature_set_service(service):
        """Set temperature on the target climate devices."""
        target_climate = component.async_extract_from_service(service)

        update_tasks = []
        for climate in target_climate:
            kwargs = {}
            for value, temp in service.data.items():
                if value in CONVERTIBLE_ATTRIBUTE:
                    kwargs[value] = convert_temperature(
                        temp,
                        hass.config.units.temperature_unit,
                        climate.temperature_unit
                    )
                else:
                    kwargs[value] = temp

            yield from climate.async_set_temperature(**kwargs)

            if not climate.should_poll:
                continue
            update_tasks.append(climate.async_update_ha_state(True))

        if update_tasks:
            yield from asyncio.wait(update_tasks, loop=hass.loop)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_TEMPERATURE, async_temperature_set_service,
        descriptions.get(SERVICE_SET_TEMPERATURE),
        schema=SET_TEMPERATURE_SCHEMA)

    @asyncio.coroutine
    def async_humidity_set_service(service):
        """Set humidity on the target climate devices."""
        target_climate = component.async_extract_from_service(service)

        humidity = service.data.get(ATTR_HUMIDITY)

        update_tasks = []
        for climate in target_climate:
            yield from climate.async_set_humidity(humidity)
            if not climate.should_poll:
                continue
            update_tasks.append(climate.async_update_ha_state(True))

        if update_tasks:
            yield from asyncio.wait(update_tasks, loop=hass.loop)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_HUMIDITY, async_humidity_set_service,
        descriptions.get(SERVICE_SET_HUMIDITY),
        schema=SET_HUMIDITY_SCHEMA)

    @asyncio.coroutine
    def async_fan_mode_set_service(service):
        """Set fan mode on target climate devices."""
        target_climate = component.async_extract_from_service(service)

        fan = service.data.get(ATTR_FAN_MODE)

        update_tasks = []
        for climate in target_climate:
            yield from climate.async_set_fan_mode(fan)
            if not climate.should_poll:
                continue
            update_tasks.append(climate.async_update_ha_state(True))

        if update_tasks:
            yield from asyncio.wait(update_tasks, loop=hass.loop)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_FAN_MODE, async_fan_mode_set_service,
        descriptions.get(SERVICE_SET_FAN_MODE),
        schema=SET_FAN_MODE_SCHEMA)

    @asyncio.coroutine
    def async_operation_set_service(service):
        """Set operating mode on the target climate devices."""
        target_climate = component.async_extract_from_service(service)

        operation_mode = service.data.get(ATTR_OPERATION_MODE)

        update_tasks = []
        for climate in target_climate:
            yield from climate.async_set_operation_mode(operation_mode)
            if not climate.should_poll:
                continue
            update_tasks.append(climate.async_update_ha_state(True))

        if update_tasks:
            yield from asyncio.wait(update_tasks, loop=hass.loop)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_OPERATION_MODE, async_operation_set_service,
        descriptions.get(SERVICE_SET_OPERATION_MODE),
        schema=SET_OPERATION_MODE_SCHEMA)

    @asyncio.coroutine
    def async_swing_set_service(service):
        """Set swing mode on the target climate devices."""
        target_climate = component.async_extract_from_service(service)

        swing_mode = service.data.get(ATTR_SWING_MODE)

        update_tasks = []
        for climate in target_climate:
            yield from climate.async_set_swing_mode(swing_mode)
            if not climate.should_poll:
                continue
            update_tasks.append(climate.async_update_ha_state(True))

        if update_tasks:
            yield from asyncio.wait(update_tasks, loop=hass.loop)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_SWING_MODE, async_swing_set_service,
        descriptions.get(SERVICE_SET_SWING_MODE),
        schema=SET_SWING_MODE_SCHEMA)

    return True


class ClimateDevice(Entity):
    """Representation of a climate device."""

    # pylint: disable=no-self-use
    @property
    def state(self):
        """Return the current state."""
        if self.current_operation:
            return self.current_operation
        return STATE_UNKNOWN

    @property
    def precision(self):
        """Return the precision of the system."""
        if self.unit_of_measurement == TEMP_CELSIUS:
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

        if self.target_temperature_step is not None:
            data[ATTR_TARGET_TEMP_STEP] = self.target_temperature_step

        target_temp_high = self.target_temperature_high
        if target_temp_high is not None:
            data[ATTR_TARGET_TEMP_HIGH] = show_temp(
                self.hass, self.target_temperature_high, self.temperature_unit,
                self.precision)
            data[ATTR_TARGET_TEMP_LOW] = show_temp(
                self.hass, self.target_temperature_low, self.temperature_unit,
                self.precision)

        humidity = self.target_humidity
        if humidity is not None:
            data[ATTR_HUMIDITY] = humidity
            data[ATTR_CURRENT_HUMIDITY] = self.current_humidity
            data[ATTR_MIN_HUMIDITY] = self.min_humidity
            data[ATTR_MAX_HUMIDITY] = self.max_humidity

        fan_mode = self.current_fan_mode
        if fan_mode is not None:
            data[ATTR_FAN_MODE] = fan_mode
            if self.fan_list:
                data[ATTR_FAN_LIST] = self.fan_list

        operation_mode = self.current_operation
        if operation_mode is not None:
            data[ATTR_OPERATION_MODE] = operation_mode
            if self.operation_list:
                data[ATTR_OPERATION_LIST] = self.operation_list

        is_hold = self.current_hold_mode
        if is_hold is not None:
            data[ATTR_HOLD_MODE] = is_hold

        swing_mode = self.current_swing_mode
        if swing_mode is not None:
            data[ATTR_SWING_MODE] = swing_mode
            if self.swing_list:
                data[ATTR_SWING_LIST] = self.swing_list

        is_away = self.is_away_mode_on
        if is_away is not None:
            data[ATTR_AWAY_MODE] = STATE_ON if is_away else STATE_OFF

        is_aux_heat = self.is_aux_heat_on
        if is_aux_heat is not None:
            data[ATTR_AUX_HEAT] = STATE_ON if is_aux_heat else STATE_OFF

        return data

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement to display."""
        return self.hass.config.units.temperature_unit

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

    def set_fan_mode(self, fan):
        """Set new target fan mode."""
        raise NotImplementedError()

    def async_set_fan_mode(self, fan):
        """Set new target fan mode.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.set_fan_mode, fan)

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

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return convert_temperature(7, TEMP_CELSIUS, self.temperature_unit)

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return convert_temperature(35, TEMP_CELSIUS, self.temperature_unit)

    @property
    def min_humidity(self):
        """Return the minimum humidity."""
        return 30

    @property
    def max_humidity(self):
        """Return the maximum humidity."""
        return 99
