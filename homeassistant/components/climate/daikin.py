"""
Support for the Daikin HVAC.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.daikin/
"""
import logging
import voluptuous as vol

from homeassistant.components.climate import (
    ClimateDevice,
    ATTR_OPERATION_MODE,

    STATE_OFF,
    STATE_AUTO, STATE_HEAT, STATE_COOL, STATE_DRY, STATE_FAN_ONLY,

    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_FAN_MODE,
    SUPPORT_OPERATION_MODE, SUPPORT_SWING_MODE,
    PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_HOST, CONF_NAME,
    TEMP_CELSIUS, ATTR_TEMPERATURE)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pydaikin==0.4']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=None): cv.string,
})

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE |
                 SUPPORT_FAN_MODE |
                 SUPPORT_OPERATION_MODE |
                 SUPPORT_SWING_MODE)

HA_STATE_TO_DAIKIN = {
    STATE_FAN_ONLY: 'fan',
    STATE_DRY: 'dry',
    STATE_COOL: 'cool',
    STATE_HEAT: 'hot',
    STATE_AUTO: 'auto',
    STATE_OFF: 'off',
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Daikin HVAC platform."""
    devices = []

    name = config.get(CONF_NAME, None)

    if discovery_info is not None:
        host = discovery_info['ip']
        _LOGGER.info("Discovered a Daikin AC %s", host)
    else:
        host = config.get(CONF_HOST)
        _LOGGER.info("Added Daikin AC %s", host)

    devices.append(setup_hvac(host, name))
    add_devices(devices, True)


def setup_hvac(host, name):
    """Setup Daikin HVAC device."""
    import pydaikin.appliance as appliance
    device = appliance.Appliance(host)

    if name is None:
        name = device.values['name']

    return DaikinHVAC(device, name)


class DaikinHVAC(ClimateDevice):
    """Representation of a Daikin HVAC."""

    def __init__(self, device, name):
        """Initialize the climate device."""
        import pydaikin.appliance as appliance

        self._name = name
        self._device = device

        self._operation_list = list(
            map(str.title, set(HA_STATE_TO_DAIKIN.values()))
        )

        self._fan_list = list(
            map(str.title, appliance.daikin_values('f_rate'))
        )
        self._swing_list = list(
            map(str.title, appliance.daikin_values('f_dir'))
        )

        self._current_temperature = None
        self._target_temperature = None
        self._current_fan_mode = None
        self._current_swing_mode = None

    @property
    def unique_id(self):
        """Return the ID of this AC."""
        return "{}.{}".format(self.__class__, self._device.ip)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def name(self):
        """Return the name of the thermostat, if any."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        self._current_temperature = self.settings('htemp', True)

        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        self._target_temperature = self.settings('stemp', True)

        return self._target_temperature

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        settings = {}

        if kwargs.get(ATTR_OPERATION_MODE) is not None:
            operation_mode = kwargs.get(ATTR_OPERATION_MODE)
            current_operation = operation_mode.lower()
            if current_operation is not None:
                settings['mode'] = current_operation

        if kwargs.get(ATTR_TEMPERATURE) is not None:
            temperature = kwargs.get(ATTR_TEMPERATURE)
            try:
                self._target_temperature = int(temperature)
                settings['stemp'] = str(self._target_temperature)
            except ValueError:
                _LOGGER.error("Invalid temperature %s", temperature)

        if settings:
            self._device.set(settings)
            self.schedule_update_ha_state()

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        import re

        # Daikin can return also internal states auto-1 or auto-7
        # and we need to translate them as AUTO
        current_operation = re.sub(
            '[^a-z]',
            '',
            self._device.represent('mode')[1]
        )
        return current_operation.title()

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return self._operation_list

    def set_operation_mode(self, operation_mode):
        """Set HVAC mode."""
        current_operation = operation_mode.lower()

        if current_operation is not None:
            self._device.set({"mode": current_operation})
            self.schedule_update_ha_state()
        else:
            _LOGGER.error("Invalid operation mode %s", operation_mode)

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        self._current_fan_mode = self._device.represent('f_rate')[1]

        return self._current_fan_mode.title()

    def set_fan_mode(self, fan):
        """Set fan mode."""
        if fan in self._fan_list:
            self._device.set({"f_rate": fan.lower()})
            self._current_fan_mode = fan
            self.schedule_update_ha_state()
        else:
            _LOGGER.error("Invalid fan mode %s", fan)

    @property
    def fan_list(self):
        """List of available fan modes."""
        return self._fan_list

    @property
    def current_swing_mode(self):
        """Return the fan setting."""
        self._current_swing_mode = self._device.represent('f_dir')[1]

        return self._current_swing_mode.title()

    def set_swing_mode(self, swing_mode):
        """Set new target temperature."""
        if swing_mode in self._swing_list:
            self._device.set({"f_dir": swing_mode.lower()})
            self._current_swing_mode = swing_mode
            self.schedule_update_ha_state()
        else:
            _LOGGER.error("Invalid swing mode %s", swing_mode)

    @property
    def swing_list(self):
        """List of available swing modes."""
        return self._swing_list

    def settings(self, key, cast_to_float=False):
        """Retrieve device settings from API library cache."""
        value = None
        if key in self._device.values:
            value = self._device.values[key]
            if value == "-" or value == "--":
                value = None
            elif cast_to_float:
                try:
                    value = float(value)
                except ValueError:
                    value = None

        else:
            _LOGGER.error("Invalid setting requested for key %s", key)

        return value

    def update(self):
        """Retrieve latest state."""
        import pydaikin.appliance as appliance

        for resource in appliance.HTTP_RESOURCES:
            self._device.values.update(self._device.get_resource(resource))
