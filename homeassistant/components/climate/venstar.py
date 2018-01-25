"""
Support for Venstar WiFi Thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.venstar/
"""
import logging

import voluptuous as vol

from homeassistant.components.climate import (
    ATTR_OPERATION_MODE, ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW,
    PLATFORM_SCHEMA, STATE_AUTO, STATE_COOL, STATE_HEAT, SUPPORT_FAN_MODE,
    SUPPORT_OPERATION_MODE, SUPPORT_TARGET_HUMIDITY,
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_TARGET_TEMPERATURE_HIGH,
    SUPPORT_TARGET_TEMPERATURE_LOW, ClimateDevice)
from homeassistant.const import (
    ATTR_TEMPERATURE, CONF_HOST, CONF_PASSWORD, CONF_SSL, CONF_TIMEOUT,
    CONF_USERNAME, PRECISION_WHOLE, STATE_OFF, STATE_ON, TEMP_CELSIUS,
    TEMP_FAHRENHEIT)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['venstarcolortouch==0.5']

_LOGGER = logging.getLogger(__name__)

ATTR_FAN_STATE = 'fan_state'
ATTR_HVAC_STATE = 'hvac_state'

DEFAULT_SSL = False

VALID_FAN_STATES = [STATE_ON, STATE_AUTO]
VALID_THERMOSTAT_MODES = [STATE_HEAT, STATE_COOL, STATE_OFF, STATE_AUTO]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
    vol.Optional(CONF_TIMEOUT, default=5):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
    vol.Optional(CONF_USERNAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Venstar thermostat."""
    import venstarcolortouch

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    host = config.get(CONF_HOST)
    timeout = config.get(CONF_TIMEOUT)

    if config.get(CONF_SSL):
        proto = 'https'
    else:
        proto = 'http'

    client = venstarcolortouch.VenstarColorTouch(
        addr=host, timeout=timeout, user=username, password=password,
        proto=proto)

    add_devices([VenstarThermostat(client)], True)


class VenstarThermostat(ClimateDevice):
    """Representation of a Venstar thermostat."""

    def __init__(self, client):
        """Initialize the thermostat."""
        self._client = client

    def update(self):
        """Update the data from the thermostat."""
        info_success = self._client.update_info()
        sensor_success = self._client.update_sensors()
        if not info_success or not sensor_success:
            _LOGGER.error("Failed to update data")

    @property
    def supported_features(self):
        """Return the list of supported features."""
        features = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE |
                    SUPPORT_OPERATION_MODE)

        if self._client.mode == self._client.MODE_AUTO:
            features |= (SUPPORT_TARGET_TEMPERATURE_HIGH |
                         SUPPORT_TARGET_TEMPERATURE_LOW)

        if self._client.hum_active == 1:
            features |= SUPPORT_TARGET_HUMIDITY

        return features

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._client.name

    @property
    def precision(self):
        """Return the precision of the system.

        Venstar temperature values are passed back and forth in the
        API as whole degrees C or F.
        """
        return PRECISION_WHOLE

    @property
    def temperature_unit(self):
        """Return the unit of measurement, as defined by the API."""
        if self._client.tempunits == self._client.TEMPUNITS_F:
            return TEMP_FAHRENHEIT
        else:
            return TEMP_CELSIUS

    @property
    def fan_list(self):
        """Return the list of available fan modes."""
        return VALID_FAN_STATES

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return VALID_THERMOSTAT_MODES

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._client.get_indoor_temp()

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._client.get_indoor_humidity()

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        if self._client.mode == self._client.MODE_HEAT:
            return STATE_HEAT
        elif self._client.mode == self._client.MODE_COOL:
            return STATE_COOL
        elif self._client.mode == self._client.MODE_AUTO:
            return STATE_AUTO
        else:
            return STATE_OFF

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        if self._client.fan == self._client.FAN_AUTO:
            return STATE_AUTO
        else:
            return STATE_ON

    @property
    def device_state_attributes(self):
        """Return the optional state attributes."""
        return {
            ATTR_FAN_STATE: self._client.fanstate,
            ATTR_HVAC_STATE: self._client.state,
        }

    @property
    def target_temperature(self):
        """Return the target temperature we try to reach."""
        if self._client.mode == self._client.MODE_HEAT:
            return self._client.heattemp
        elif self._client.mode == self._client.MODE_COOL:
            return self._client.cooltemp
        else:
            return None

    @property
    def target_temperature_low(self):
        """Return the lower bound temp if auto mode is on."""
        if self._client.mode == self._client.MODE_AUTO:
            return self._client.heattemp
        else:
            return None

    @property
    def target_temperature_high(self):
        """Return the upper bound temp if auto mode is on."""
        if self._client.mode == self._client.MODE_AUTO:
            return self._client.cooltemp
        else:
            return None

    @property
    def target_humidity(self):
        """Return the humidity we try to reach."""
        return self._client.hum_setpoint

    @property
    def min_humidity(self):
        """Return the minimum humidity. Hardcoded to 0 in API."""
        return 0

    @property
    def max_humidity(self):
        """Return the maximum humidity. Hardcoded to 60 in API."""
        return 60

    def _set_operation_mode(self, operation_mode):
        """Change the operation mode (internal)."""
        if operation_mode == STATE_HEAT:
            success = self._client.set_mode(self._client.MODE_HEAT)
        elif operation_mode == STATE_COOL:
            success = self._client.set_mode(self._client.MODE_COOL)
        elif operation_mode == STATE_AUTO:
            success = self._client.set_mode(self._client.MODE_AUTO)
        else:
            success = self._client.set_mode(self._client.MODE_OFF)

        if not success:
            _LOGGER.error("Failed to change the operation mode")
        return success

    def set_temperature(self, **kwargs):
        """Set a new target temperature."""
        set_temp = True
        operation_mode = kwargs.get(ATTR_OPERATION_MODE, self._client.mode)
        temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        temperature = kwargs.get(ATTR_TEMPERATURE)

        if operation_mode != self._client.mode:
            set_temp = self._set_operation_mode(operation_mode)

        if set_temp:
            if operation_mode == self._client.MODE_HEAT:
                success = self._client.set_setpoints(
                    temperature, self._client.cooltemp)
            elif operation_mode == self._client.MODE_COOL:
                success = self._client.set_setpoints(
                    self._client.heattemp, temperature)
            elif operation_mode == self._client.MODE_AUTO:
                success = self._client.set_setpoints(temp_low, temp_high)
            else:
                _LOGGER.error("The thermostat is currently not in a mode "
                              "that supports target temperature")

            if not success:
                _LOGGER.error("Failed to change the temperature")

    def set_fan_mode(self, fan):
        """Set new target fan mode."""
        if fan == STATE_ON:
            success = self._client.set_fan(self._client.FAN_ON)
        else:
            success = self._client.set_fan(self._client.FAN_AUTO)

        if not success:
            _LOGGER.error("Failed to change the fan mode")

    def set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        self._set_operation_mode(operation_mode)

    def set_humidity(self, humidity):
        """Set new target humidity."""
        success = self._client.set_hum_setpoint(humidity)

        if not success:
            _LOGGER.error("Failed to change the target humidity level")
