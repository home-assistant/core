"""
homeassistant.components.sensor.dweet
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Displays values from Dweet.io..

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.dweet/
"""
from datetime import timedelta
import logging

import homeassistant.util as util
from homeassistant.util import Throttle
from homeassistant.helpers.entity import Entity
from homeassistant.const import STATE_UNKNOWN

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Dweet.io Sensor'
CONF_DEVICE = 'device'

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)


# pylint: disable=unused-variable
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Setup the Dweet sensor. """

    import dweepy

    device = config.get('device')

    if device is None:
        _LOGGER.error('Not all required config keys present: %s',
                      ', '.join(CONF_DEVICE))
        return False

    try:
        dweepy.get_latest_dweet_for(device)
    except dweepy.DweepyError:
        _LOGGER.error("Device/thing '%s' could not be found", device)
        return False

    dweet = DweetData(device)

    add_devices([DweetSensor(dweet,
                             config.get('name', DEFAULT_NAME),
                             config.get('variable'),
                             config.get('unit_of_measurement'),
                             config.get('correction_factor', None),
                             config.get('decimal_places', None))])


class DweetSensor(Entity):
    """ Implements a Dweet sensor. """

    def __init__(self, dweet, name, variable, unit_of_measurement, corr_factor,
                 decimal_places):
        self.dweet = dweet
        self._name = name
        self._variable = variable
        self._state = STATE_UNKNOWN
        self._unit_of_measurement = unit_of_measurement
        self._corr_factor = corr_factor
        self._decimal_places = decimal_places
        self.update()

    @property
    def name(self):
        """ The name of the sensor. """
        return self._name

    @property
    def unit_of_measurement(self):
        """ Unit the value is expressed in. """
        return self._unit_of_measurement

    @property
    def state(self):
        """ Returns the state. """
        values = self.dweet.data

        if values is not None:
            value = util.extract_value_json(values[0]['content'],
                                            self._variable)
            if self._corr_factor is not None:
                value = float(value) * float(self._corr_factor)
            if self._decimal_places is not None:
                value = round(value, self._decimal_places)
            if self._decimal_places == 0:
                value = int(value)
            return value
        else:
            return STATE_UNKNOWN

    def update(self):
        """ Gets the latest data from REST API. """
        self.dweet.update()


# pylint: disable=too-few-public-methods
class DweetData(object):
    """ Class for handling the data retrieval. """

    def __init__(self, device):
        self._device = device
        self.data = dict()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """ Gets the latest data from Dweet.io. """
        import dweepy

        try:
            self.data = dweepy.get_latest_dweet_for(self._device)
        except dweepy.DweepyError:
            _LOGGER.error("Device '%s' could not be found", self._device)
            self.data = None
