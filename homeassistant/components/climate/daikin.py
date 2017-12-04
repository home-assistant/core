"""
Support for the Daikin HVAC

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.daikin/
"""
import logging
import voluptuous as vol

from homeassistant.components.climate import (
    ClimateDevice,
    STATE_OFF, STATE_COOL, STATE_HEAT, STATE_AUTO, STATE_DRY, STATE_FAN_ONLY,
    STATE_ECO, STATE_PERFORMANCE,
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_TARGET_HUMIDITY,
    SUPPORT_FAN_MODE,
    SUPPORT_OPERATION_MODE, SUPPORT_SWING_MODE,
    PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_IP_ADDRESS, CONF_NAME,
    TEMP_CELSIUS, ATTR_TEMPERATURE)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pydaikin==0.4']

HA_STATE_TO_DAIKIN = {
    STATE_OFF: 'off',
    STATE_HEAT: 'hot',
    STATE_COOL: 'cool',
    STATE_FAN_ONLY: 'fan',
    STATE_DRY: 'dry',
    STATE_AUTO: 'auto',
    STATE_ECO: 'auto-1',
    STATE_PERFORMANCE: 'auto-7',
}

DAIKIN_OPERATION_LIST = {
    STATE_OFF: 'off',
    STATE_HEAT: 'hot',
    STATE_COOL: 'cool',
    STATE_FAN_ONLY: 'fan',
    STATE_DRY: 'dry',
    STATE_AUTO: 'auto',
}

DAIKIN_STATE_TO_HA = {value: key for key, value in HA_STATE_TO_DAIKIN.items()}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_IP_ADDRESS): cv.string,
    vol.Optional(CONF_NAME, default=None): cv.string,
})

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_TARGET_HUMIDITY |
                 SUPPORT_FAN_MODE |
                 SUPPORT_OPERATION_MODE |
                 SUPPORT_SWING_MODE)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Daikin HVAC platform."""
    devices = []

    name = config.get(CONF_NAME, None)

    if discovery_info is not None:
        ip_address = discovery_info['ip']
        devices.append(setup_hvac(ip_address, name))
    else:
        ip_address = config.get(CONF_IP_ADDRESS, None)
        devices.append(setup_hvac(ip_address, name))

    add_devices(devices)


def setup_hvac(ip_address, name):
    if ip_address is None:
        _LOGGER.error("Missing required configuration items %s",
                      CONF_IP_ADDRESS)
        return False

    import pydaikin.appliance as appliance
    device = appliance.Appliance(ip_address)

    if name is None:
        name = device.values['name']

    return DaikinHVAC(device, name)


class DaikinHVAC(ClimateDevice):
    """Representation of a Daikin HVAC."""

    def __init__(self, device, name):
        import pydaikin.appliance as appliance

        """Initialize the HVAC."""
        self._name = name
        self._device = device

        self._current_temperature = self.settings('htemp', True)
        self._operation_list = list(DAIKIN_OPERATION_LIST.values())
        self._fan_list = appliance.daikin_values('f_rate')
        self._swing_list = appliance.daikin_values('f_dir')

        self._target_temperature = None
        self._current_humidity = None
        self._target_humidity = None
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
    def should_poll(self):
        """Polling needed for a demo climate device."""
        return True

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

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)

        if temperature is None:
            return

        self._device.set({"temp": temperature})
        self._target_temperature = temperature

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        state = self._device.represent('mode')[1]

        current_operation = DAIKIN_STATE_TO_HA.get(state)
        if current_operation in [STATE_ECO, STATE_PERFORMANCE]:
            current_operation = STATE_AUTO

        return current_operation

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return self._operation_list

    def set_operation_mode(self, operation_mode):
        """Set HVAC mode (auto, auxHeatOnly, cool, heat, off)."""

        current_operation = HA_STATE_TO_DAIKIN.get(operation_mode)
        self._device.set({"mode": current_operation})

    @property
    def current_humidity(self):
        """Return the current humidity."""
        self._current_humidity = self._device.represent('shum')[1]

        return self._current_humidity

    def set_humidity(self, humidity):
        """Set new target temperature."""
        self._target_humidity = humidity
        self._device.set({"shum": humidity})

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        self._current_fan_mode = self._device.represent('f_rate')[1]

        return self._current_fan_mode

    def set_fan_mode(self, fan):
        """Set fan mode."""
        self._device.set({"f_rate": fan})
        self._current_fan_mode = fan

    @property
    def fan_list(self):
        """List of available fan modes."""
        return self._fan_list

    @property
    def current_swing_mode(self):
        """Return the fan setting."""
        self._current_swing_mode = self._device.represent('f_dir')[1]

        return self._current_swing_mode

    def set_swing_mode(self, swing_mode):
        """Set new target temperature."""
        self._device.set({"f_dir": swing_mode})
        self._current_swing_mode = swing_mode

    @property
    def swing_list(self):
        """List of available swing modes."""
        return self._swing_list

    def settings(self, key, cast_to_float=False):
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
        import pydaikin.appliance as appliance

        """Get the latest data."""
        for resource in appliance.HTTP_RESOURCES:
            self._device.values.update(self._device.get_resource(resource))
