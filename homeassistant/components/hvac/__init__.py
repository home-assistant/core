"""
Provides functionality to interact with hvacs.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/hvac/
"""
import logging
import os
from numbers import Number

from homeassistant.helpers.entity_component import EntityComponent

from homeassistant.config import load_yaml_config_file
import homeassistant.util as util
from homeassistant.util.temperature import convert as convert_temperature
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_TEMPERATURE, STATE_ON, STATE_OFF, STATE_UNKNOWN,
    TEMP_CELSIUS)

DOMAIN = "hvac"

ENTITY_ID_FORMAT = DOMAIN + ".{}"
SCAN_INTERVAL = 60

SERVICE_SET_AWAY_MODE = "set_away_mode"
SERVICE_SET_AUX_HEAT = "set_aux_heat"
SERVICE_SET_TEMPERATURE = "set_temperature"
SERVICE_SET_FAN_MODE = "set_fan_mode"
SERVICE_SET_OPERATION_MODE = "set_operation_mode"
SERVICE_SET_SWING_MODE = "set_swing_mode"
SERVICE_SET_HUMIDITY = "set_humidity"

STATE_HEAT = "heat"
STATE_COOL = "cool"
STATE_IDLE = "idle"
STATE_AUTO = "auto"
STATE_DRY = "dry"
STATE_FAN_ONLY = "fan_only"

ATTR_CURRENT_TEMPERATURE = "current_temperature"
ATTR_MAX_TEMP = "max_temp"
ATTR_MIN_TEMP = "min_temp"
ATTR_AWAY_MODE = "away_mode"
ATTR_AUX_HEAT = "aux_heat"
ATTR_FAN_MODE = "fan_mode"
ATTR_FAN_LIST = "fan_list"
ATTR_CURRENT_HUMIDITY = "current_humidity"
ATTR_HUMIDITY = "humidity"
ATTR_MAX_HUMIDITY = "max_humidity"
ATTR_MIN_HUMIDITY = "min_humidity"
ATTR_OPERATION_MODE = "operation_mode"
ATTR_OPERATION_LIST = "operation_list"
ATTR_SWING_MODE = "swing_mode"
ATTR_SWING_LIST = "swing_list"

_LOGGER = logging.getLogger(__name__)


def set_away_mode(hass, away_mode, entity_id=None):
    """Turn all or specified hvac away mode on."""
    data = {
        ATTR_AWAY_MODE: away_mode
    }

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_AWAY_MODE, data)


def set_aux_heat(hass, aux_heat, entity_id=None):
    """Turn all or specified hvac auxillary heater on."""
    data = {
        ATTR_AUX_HEAT: aux_heat
    }

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_AUX_HEAT, data)


def set_temperature(hass, temperature, entity_id=None):
    """Set new target temperature."""
    data = {ATTR_TEMPERATURE: temperature}

    if entity_id is not None:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_TEMPERATURE, data)


def set_humidity(hass, humidity, entity_id=None):
    """Set new target humidity."""
    data = {ATTR_HUMIDITY: humidity}

    if entity_id is not None:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_HUMIDITY, data)


def set_fan_mode(hass, fan, entity_id=None):
    """Turn all or specified hvac fan mode on."""
    data = {ATTR_FAN_MODE: fan}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_FAN_MODE, data)


def set_operation_mode(hass, operation_mode, entity_id=None):
    """Set new target operation mode."""
    data = {ATTR_OPERATION_MODE: operation_mode}

    if entity_id is not None:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_OPERATION_MODE, data)


def set_swing_mode(hass, swing_mode, entity_id=None):
    """Set new target swing mode."""
    data = {ATTR_SWING_MODE: swing_mode}

    if entity_id is not None:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_SWING_MODE, data)


# pylint: disable=too-many-branches
def setup(hass, config):
    """Setup hvacs."""
    _LOGGER.warning('This component has been deprecated in favour of'
                    ' the "climate" component and will be removed '
                    'in the future. Please upgrade.')
    component = EntityComponent(_LOGGER, DOMAIN, hass, SCAN_INTERVAL)
    component.setup(config)

    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    def away_mode_set_service(service):
        """Set away mode on target hvacs."""
        target_hvacs = component.extract_from_service(service)

        away_mode = service.data.get(ATTR_AWAY_MODE)

        if away_mode is None:
            _LOGGER.error(
                "Received call to %s without attribute %s",
                SERVICE_SET_AWAY_MODE, ATTR_AWAY_MODE)
            return

        for hvac in target_hvacs:
            if away_mode:
                hvac.turn_away_mode_on()
            else:
                hvac.turn_away_mode_off()

            if hvac.should_poll:
                hvac.update_ha_state(True)

    hass.services.register(
        DOMAIN, SERVICE_SET_AWAY_MODE, away_mode_set_service,
        descriptions.get(SERVICE_SET_AWAY_MODE))

    def aux_heat_set_service(service):
        """Set auxillary heater on target hvacs."""
        target_hvacs = component.extract_from_service(service)

        aux_heat = service.data.get(ATTR_AUX_HEAT)

        if aux_heat is None:
            _LOGGER.error(
                "Received call to %s without attribute %s",
                SERVICE_SET_AUX_HEAT, ATTR_AUX_HEAT)
            return

        for hvac in target_hvacs:
            if aux_heat:
                hvac.turn_aux_heat_on()
            else:
                hvac.turn_aux_heat_off()

            if hvac.should_poll:
                hvac.update_ha_state(True)

    hass.services.register(
        DOMAIN, SERVICE_SET_AUX_HEAT, aux_heat_set_service,
        descriptions.get(SERVICE_SET_AUX_HEAT))

    def temperature_set_service(service):
        """Set temperature on the target hvacs."""
        target_hvacs = component.extract_from_service(service)

        temperature = util.convert(
            service.data.get(ATTR_TEMPERATURE), float)

        if temperature is None:
            _LOGGER.error(
                "Received call to %s without attribute %s",
                SERVICE_SET_TEMPERATURE, ATTR_TEMPERATURE)
            return

        for hvac in target_hvacs:
            hvac.set_temperature(convert_temperature(
                temperature, hass.config.units.temperature_unit,
                hvac.unit_of_measurement))

            if hvac.should_poll:
                hvac.update_ha_state(True)

    hass.services.register(
        DOMAIN, SERVICE_SET_TEMPERATURE, temperature_set_service,
        descriptions.get(SERVICE_SET_TEMPERATURE))

    def humidity_set_service(service):
        """Set humidity on the target hvacs."""
        target_hvacs = component.extract_from_service(service)

        humidity = service.data.get(ATTR_HUMIDITY)

        if humidity is None:
            _LOGGER.error(
                "Received call to %s without attribute %s",
                SERVICE_SET_HUMIDITY, ATTR_HUMIDITY)
            return

        for hvac in target_hvacs:
            hvac.set_humidity(humidity)

            if hvac.should_poll:
                hvac.update_ha_state(True)

    hass.services.register(
        DOMAIN, SERVICE_SET_HUMIDITY, humidity_set_service,
        descriptions.get(SERVICE_SET_HUMIDITY))

    def fan_mode_set_service(service):
        """Set fan mode on target hvacs."""
        target_hvacs = component.extract_from_service(service)

        fan = service.data.get(ATTR_FAN_MODE)

        if fan is None:
            _LOGGER.error(
                "Received call to %s without attribute %s",
                SERVICE_SET_FAN_MODE, ATTR_FAN_MODE)
            return

        for hvac in target_hvacs:
            hvac.set_fan_mode(fan)

            if hvac.should_poll:
                hvac.update_ha_state(True)

    hass.services.register(
        DOMAIN, SERVICE_SET_FAN_MODE, fan_mode_set_service,
        descriptions.get(SERVICE_SET_FAN_MODE))

    def operation_set_service(service):
        """Set operating mode on the target hvacs."""
        target_hvacs = component.extract_from_service(service)

        operation_mode = service.data.get(ATTR_OPERATION_MODE)

        if operation_mode is None:
            _LOGGER.error(
                "Received call to %s without attribute %s",
                SERVICE_SET_OPERATION_MODE, ATTR_OPERATION_MODE)
            return

        for hvac in target_hvacs:
            hvac.set_operation_mode(operation_mode)

            if hvac.should_poll:
                hvac.update_ha_state(True)

    hass.services.register(
        DOMAIN, SERVICE_SET_OPERATION_MODE, operation_set_service,
        descriptions.get(SERVICE_SET_OPERATION_MODE))

    def swing_set_service(service):
        """Set swing mode on the target hvacs."""
        target_hvacs = component.extract_from_service(service)

        swing_mode = service.data.get(ATTR_SWING_MODE)

        if swing_mode is None:
            _LOGGER.error(
                "Received call to %s without attribute %s",
                SERVICE_SET_SWING_MODE, ATTR_SWING_MODE)
            return

        for hvac in target_hvacs:
            hvac.set_swing_mode(swing_mode)

            if hvac.should_poll:
                hvac.update_ha_state(True)

    hass.services.register(
        DOMAIN, SERVICE_SET_SWING_MODE, swing_set_service,
        descriptions.get(SERVICE_SET_SWING_MODE))
    return True


class HvacDevice(Entity):
    """Representation of a hvac."""

    # pylint: disable=too-many-public-methods,no-self-use
    @property
    def state(self):
        """Return the current state."""
        return self.current_operation or STATE_UNKNOWN

    @property
    def state_attributes(self):
        """Return the optional state attributes."""
        data = {
            ATTR_CURRENT_TEMPERATURE:
            self._convert_for_display(self.current_temperature),
            ATTR_MIN_TEMP: self._convert_for_display(self.min_temp),
            ATTR_MAX_TEMP: self._convert_for_display(self.max_temp),
            ATTR_TEMPERATURE:
            self._convert_for_display(self.target_temperature),
        }

        humidity = self.target_humidity
        if humidity is not None:
            data[ATTR_HUMIDITY] = humidity
            data[ATTR_CURRENT_HUMIDITY] = self.current_humidity
            data[ATTR_MIN_HUMIDITY] = self.min_humidity
            data[ATTR_MAX_HUMIDITY] = self.max_humidity

        fan_mode = self.current_fan_mode
        if fan_mode is not None:
            data[ATTR_FAN_MODE] = fan_mode
            data[ATTR_FAN_LIST] = self.fan_list

        operation_mode = self.current_operation
        if operation_mode is not None:
            data[ATTR_OPERATION_MODE] = operation_mode
            data[ATTR_OPERATION_LIST] = self.operation_list

        swing_mode = self.current_swing_mode
        if swing_mode is not None:
            data[ATTR_SWING_MODE] = swing_mode
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
        """Return the unit of measurement."""
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
        """List of available operation modes."""
        return None

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return None

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        raise NotImplementedError

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        return None

    @property
    def is_aux_heat_on(self):
        """Return true if away mode is on."""
        return None

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        return None

    @property
    def fan_list(self):
        """List of available fan modes."""
        return None

    @property
    def current_swing_mode(self):
        """Return the fan setting."""
        return None

    @property
    def swing_list(self):
        """List of available swing modes."""
        return None

    def set_temperature(self, temperature):
        """Set new target temperature."""
        raise NotImplementedError()

    def set_humidity(self, humidity):
        """Set new target humidity."""
        raise NotImplementedError()

    def set_fan_mode(self, fan):
        """Set new target fan mode."""
        raise NotImplementedError()

    def set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        raise NotImplementedError()

    def set_swing_mode(self, swing_mode):
        """Set new target swing operation."""
        raise NotImplementedError()

    def turn_away_mode_on(self):
        """Turn away mode on."""
        raise NotImplementedError()

    def turn_away_mode_off(self):
        """Turn away mode off."""
        raise NotImplementedError()

    def turn_aux_heat_on(self):
        """Turn auxillary heater on."""
        raise NotImplementedError()

    def turn_aux_heat_off(self):
        """Turn auxillary heater off."""
        raise NotImplementedError()

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return convert_temperature(19, TEMP_CELSIUS, self.unit_of_measurement)

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return convert_temperature(30, TEMP_CELSIUS, self.unit_of_measurement)

    @property
    def min_humidity(self):
        """Return the minimum humidity."""
        return 30

    @property
    def max_humidity(self):
        """Return the maximum humidity."""
        return 99

    def _convert_for_display(self, temp):
        """Convert temperature into preferred units for display purposes."""
        if temp is None or not isinstance(temp, Number):
            return temp

        value = convert_temperature(temp, self.unit_of_measurement,
                                    self.hass.config.units.temperature_unit)

        if self.hass.config.units.temperature_unit is TEMP_CELSIUS:
            decimal_count = 1
        else:
            # Users of fahrenheit generally expect integer units.
            decimal_count = 0

        return round(value, decimal_count)
