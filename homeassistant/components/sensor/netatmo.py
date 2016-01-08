"""
homeassistant.components.sensor.netatmo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
NetAtmo Weather Service service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/...
"""
import logging
from datetime import timedelta

from homeassistant.const import (CONF_API_KEY, CONF_USERNAME, CONF_PASSWORD, TEMP_CELCIUS, TEMP_FAHRENHEIT)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = [
    'https://github.com/HydrelioxGitHub/netatmo-api-python/archive/'
    'f468d0926b1bc018df66896f5d67585343b56dda.zip']

_LOGGER = logging.getLogger(__name__)
SENSOR_TYPES = {
    'temperature': ['Temperature', ''],
    'humidity': ['Humidity', '%']
}

# Return cached results if last scan was less then this time ago
# NetAtmo Data is uploaded to server every 10mn so this time should not be under
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=600)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Get the NetAtmo sensor. """

    try:
        from lnetatmo import lnetatmo

    except ImportError:
        _LOGGER.exception(
            "Unable to import lnetatmo. "
            "Did you maybe not install the package ?")

        return False

    SENSOR_TYPES['temperature'][1] = hass.config.temperature_unit
    unit = hass.config.temperature_unit
    authorization = lnetatmo.ClientAuth(config.get(CONF_API_KEY, None), config.get('secret_key', None), config.get(CONF_USERNAME, None), config.get(CONF_PASSWORD, None))

    if not authorization:
        _LOGGER.error(
            "Connection error "
            "Please check your settings for NatAtmo API.")
        return False

    data = NetAtmoData(authorization)

    dev = []
    try:
        for module_name, monitored_conditions in config['modules'].items():
            for variable in monitored_conditions:
                if variable not in SENSOR_TYPES:
                    _LOGGER.error('Sensor type: "%s" does not exist', variable)
                else:
                    dev.append(NetAtmoSensor(data, module_name, variable, unit))
    except KeyError:
        pass

    add_devices(dev)


# pylint: disable=too-few-public-methods
class NetAtmoSensor(Entity):
    """ Implements a NetAtmo sensor. """

    def __init__(self, netatmo_data, module_name, sensor_type, temp_unit):
        self.client_name = 'NetAtmo'
        self._name = module_name + '_' + SENSOR_TYPES[sensor_type][0]
        self.netatmo_data = netatmo_data
        self.module_name = module_name
        self.temp_unit = temp_unit
        self.type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self.update()

    @property
    def name(self):
        return '{} {}'.format(self.client_name, self._name)

    @property
    def state(self):
        """ Returns the state of the device. """
        return self._state

    @property
    def unit_of_measurement(self):
        """ Unit of measurement of this entity, if any. """
        return self._unit_of_measurement

    # pylint: disable=too-many-branches
    def update(self):
        """ Gets the latest data from NetAtmo API and updates the states. """

        self.netatmo_data.update()
        data = self.netatmo_data.data[self.module_name]

        if self.type == 'temperature':
            if self.temp_unit == TEMP_CELCIUS:
                self._state = round(data['Temperature'],
                                    1)
            elif self.temp_unit == TEMP_FAHRENHEIT:
                self._state = round(data['Temperature'],
                                    1)
            else:
                self._state = round(data['Temperature'], 1)
        elif self.type == 'humidity':
            self._state = data['Humidity']
        elif self.type == 'pressure':
            self._state = round(data.get_pressure()['press'], 0)
        elif self.type == 'clouds':
            self._state = data.get_clouds()
        elif self.type == 'rain':
            if data.get_rain():
                self._state = round(data.get_rain()['3h'], 0)
                self._unit_of_measurement = 'mm'
            else:
                self._state = 'not raining'
                self._unit_of_measurement = ''
        elif self.type == 'snow':
            if data.get_snow():
                self._state = round(data.get_snow(), 0)
                self._unit_of_measurement = 'mm'
            else:
                self._state = 'not snowing'
                self._unit_of_measurement = ''


class NetAtmoData(object):
    """ Gets the latest data from NetAtmo. """

    def __init__(self, auth):
        from lnetatmo import DeviceList

        self.auth = auth
        self.data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """ Gets the latest data from NetAtmo. """
        devList = DeviceList(self.auth)
        self.data = devList.lastData(exclude=3600)