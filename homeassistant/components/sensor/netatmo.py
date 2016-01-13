"""
homeassistant.components.sensor.netatmo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
NetAtmo Weather Service service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/...
"""
import logging
from datetime import timedelta
from homeassistant.const import (CONF_API_KEY, CONF_USERNAME, CONF_PASSWORD,
                                 TEMP_CELCIUS, TEMP_FAHRENHEIT)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.util.temperature import celcius_to_fahrenheit

REQUIREMENTS = [
    'https://github.com/HydrelioxGitHub/netatmo-api-python/archive/'
    '59d157d03db0aa167730044667591adea4457ca8.zip'
    '#lnetatmo==0.3.0.dev1']

_LOGGER = logging.getLogger(__name__)
SENSOR_TYPES = {
    'temperature': ['Temperature', ''],
    'co2': ['CO2', 'ppm'],
    'pressure': ['Pressure', 'mb'],
    'noise': ['Noise', 'dB'],
    'humidity': ['Humidity', '%']
}

# Return cached results if last scan was less then this time ago
# NetAtmo Data is uploaded to server every 10mn
# so this time should not be under
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=600)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Get the NetAtmo sensor. """

    SENSOR_TYPES['temperature'][1] = hass.config.temperature_unit
    unit = hass.config.temperature_unit
    authorization = lnetatmo.ClientAuth(config.get(CONF_API_KEY, None),
                                        config.get('secret_key', None),
                                        config.get(CONF_USERNAME, None),
                                        config.get(CONF_PASSWORD, None))

    if not authorization:
        _LOGGER.error(
            "Connection error "
            "Please check your settings for NatAtmo API.")
        return False

    data = NetAtmoData(authorization)

    dev = []
    try:
        # Iterate each module
        for module_name, monitored_conditions in config['modules'].items():
            # Test if module exist """
            if module_name not in data.get_module_names():
                _LOGGER.error('Module name: "%s" not found', module_name)
                continue
            # Only create sensor for monitored """
            for variable in monitored_conditions:
                if variable not in SENSOR_TYPES:
                    _LOGGER.error('Sensor type: "%s" does not exist', variable)
                else:
                    dev.append(
                        NetAtmoSensor(data, module_name, variable, unit))
    except KeyError:
        pass

    add_devices(dev)


# pylint: disable=too-few-public-methods
# pylint: disable=too-many-instance-attributes
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
                converted_temperature = celcius_to_fahrenheit(
                    data['Temperature'])
                self._state = round(converted_temperature, 1)
            else:
                self._state = round(data['Temperature'], 1)
        elif self.type == 'humidity':
            self._state = data['Humidity']
        elif self.type == 'noise':
            self._state = data['Noise']
        elif self.type == 'co2':
            self._state = data['CO2']
        elif self.type == 'pressure':
            self._state = round(data['Pressure'],
                                1)


class NetAtmoData(object):
    """ Gets the latest data from NetAtmo. """

    def __init__(self, auth):
        self.auth = auth
        self.data = None

    def get_module_names(self):
        """ Return all module available on the API as a list. """
        self.update()
        return self.data.keys()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """ Call the NetAtmo API to update the data. """
        import lnetatmo
        # Gets the latest data from NetAtmo. """
        dev_list = lnetatmo.DeviceList(self.auth)
        self.data = dev_list.lastData(exclude=3600)
