"""
Support for showing values from Dweet.io.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.dweet/
"""
import json
import logging
from datetime import timedelta

from homeassistant.const import CONF_VALUE_TEMPLATE, STATE_UNKNOWN
from homeassistant.helpers.entity import Entity
from homeassistant.helpers import template
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['dweepy==0.2.0']

DEFAULT_NAME = 'Dweet.io Sensor'
CONF_DEVICE = 'device'

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)


# pylint: disable=unused-variable, too-many-function-args
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Dweet sensor."""
    import dweepy

    device = config.get('device')
    value_template = config.get(CONF_VALUE_TEMPLATE)

    if None in (device, value_template):
        _LOGGER.error('Not all required config keys present: %s',
                      ', '.join(CONF_DEVICE, CONF_VALUE_TEMPLATE))
        return False

    try:
        content = json.dumps(dweepy.get_latest_dweet_for(device)[0]['content'])
    except dweepy.DweepyError:
        _LOGGER.error("Device/thing '%s' could not be found", device)
        return False

    if template.render_with_possible_json_value(hass,
                                                value_template,
                                                content) is '':
        _LOGGER.error("'%s' was not found", value_template)
        return False

    dweet = DweetData(device)

    add_devices([DweetSensor(hass,
                             dweet,
                             config.get('name', DEFAULT_NAME),
                             value_template,
                             config.get('unit_of_measurement'))])


# pylint: disable=too-many-arguments
class DweetSensor(Entity):
    """Representation of a Dweet sensor."""

    def __init__(self, hass, dweet, name, value_template, unit_of_measurement):
        """Initialize the sensor."""
        self.hass = hass
        self.dweet = dweet
        self._name = name
        self._value_template = value_template
        self._state = STATE_UNKNOWN
        self._unit_of_measurement = unit_of_measurement
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return the state."""
        if self.dweet.data is None:
            return STATE_UNKNOWN
        else:
            values = json.dumps(self.dweet.data[0]['content'])
            value = template.render_with_possible_json_value(
                self.hass, self._value_template, values)
            return value

    def update(self):
        """Get the latest data from REST API."""
        self.dweet.update()


# pylint: disable=too-few-public-methods
class DweetData(object):
    """The class for handling the data retrieval."""

    def __init__(self, device):
        """Initialize the sensor."""
        self._device = device
        self.data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from Dweet.io."""
        import dweepy

        try:
            self.data = dweepy.get_latest_dweet_for(self._device)
        except dweepy.DweepyError:
            _LOGGER.error("Device '%s' could not be found", self._device)
            self.data = None
