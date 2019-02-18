"""Climate platform that offers a climate device for the TFIAC protocol."""
import logging

import voluptuous as vol

from homeassistant.components.climate import (
    PLATFORM_SCHEMA, SUPPORT_FAN_MODE, SUPPORT_ON_OFF, SUPPORT_OPERATION_MODE,
    SUPPORT_SWING_MODE, SUPPORT_TARGET_TEMPERATURE, ClimateDevice)
from homeassistant.const import (ATTR_TEMPERATURE, CONF_HOST, STATE_OFF,
                                 STATE_ON, TEMP_FAHRENHEIT)
import homeassistant.helpers.config_validation as cv
from homeassistant.util.temperature import convert as convert_temperature

# Description of how the platform is defined
# climate:
#   platform: tfiac
#   host: 192.168.10.26

# Debug by adding this
# logger:
#   logs:
#     homeassistant.components.climate.tfiac: debug

DOMAIN = 'tfiac'

REQUIREMENTS = ['tfiac==0.0.1alpha']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
})

_LOGGER = logging.getLogger(__name__)

MIN_TEMP = 61
MAX_TEMP = 88
OPERATION_LIST = ['heat', 'selfFeel', 'dehumi', 'fan', 'cool']
FAN_LIST = ['Auto', 'Low', 'Middle', 'High']
SWING_LIST = [
    'Off',
    'Vertical',
    'Horizontal',
    'Both',
]

CURR_TEMP = 'current_temp'
TARGET_TEMP = 'target_temp'
OPERATION_MODE = 'operation'
FAN_MODE = 'fan_mode'
SWING_MODE = 'swing_mode'
ON_MODE = 'is_on'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the TFIAC climate device."""
    _LOGGER.info(discovery_info)

    host = config.get(CONF_HOST)
    if host is not None:
        add_devices([TfiacClimate(hass, host)])


class TfiacClimate(ClimateDevice):
    """TFIAC class."""

    def __init__(self, hass, host):
        """Init class."""
        from pytfiac import Tfiac
        hass.data[DOMAIN] = self
        self._client = Tfiac(host)

    def update(self):
        """Update status via socket polling."""
        self._client.update()

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return (SUPPORT_FAN_MODE | SUPPORT_ON_OFF | SUPPORT_OPERATION_MODE
                | SUPPORT_SWING_MODE | SUPPORT_TARGET_TEMPERATURE)

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return convert_temperature(MIN_TEMP, TEMP_FAHRENHEIT,
                                   self.temperature_unit)

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return convert_temperature(MAX_TEMP, TEMP_FAHRENHEIT,
                                   self.temperature_unit)

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._client.name

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._client.status['target_temp']

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_FAHRENHEIT

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._client.status['current_temp']

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return self._client.status['operation']

    @property
    def is_on(self):
        """Return true if on."""
        return STATE_ON if self._client.status[
            'current_temp'] == 'on' else STATE_OFF

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return OPERATION_LIST

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        return self._client.status['fan_mode']

    @property
    def fan_list(self):
        """Return the list of available fan modes."""
        return FAN_LIST

    @property
    def current_swing_mode(self):
        """Return the swing setting."""
        return self._client.status['swing_mode']

    @property
    def swing_list(self):
        """List of available swing modes."""
        return SWING_LIST

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self._client.set_state(TARGET_TEMP, kwargs.get(ATTR_TEMPERATURE))

    def set_operation_mode(self, operation_mode):
        """Set new operation mode."""
        self._client.set_state(OPERATION_MODE, operation_mode)

    def set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        self._client.set_state(FAN_MODE, fan_mode)

    def set_swing_mode(self, swing_mode):
        """Set new swing mode."""
        self._client.set_swing(swing_mode)

    def turn_on(self):
        """Turn device on."""
        self._client.set_state(ON_MODE, 'on')

    def turn_off(self):
        """Turn device off."""
        self._client.set_state(ON_MODE, 'off')
