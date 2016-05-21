"""
Support for the NetAtmo Weather Service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.netatmo/
"""
import logging
from datetime import timedelta
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.loader import get_component

DEPENDENCIES = ["netatmo"]

REQUIREMENTS = [
    'https://github.com/jabesq/netatmo-api-python/archive/'
    'master.zip'
    '#lnetatmo==0.4.0']

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    'temperature': ['Temperature', TEMP_CELSIUS, 'mdi:thermometer'],
    'co2':         ['CO2', 'ppm', 'mdi:cloud'],
    'pressure':    ['Pressure', 'mbar', 'mdi:gauge'],
    'noise':       ['Noise', 'dB', 'mdi:volume-high'],
    'humidity':    ['Humidity', '%', 'mdi:water-percent'],
    'rain':        ['Rain', 'mm', 'mdi:weather-rainy'],
    'sum_rain_1':  ['sum_rain_1', 'mm', 'mdi:weather-rainy'],
    'sum_rain_24': ['sum_rain_24', 'mm', 'mdi:weather-rainy'],
}

CONF_STATION = 'station'
ATTR_MODULE = 'modules'

# Return cached results if last scan was less then this time ago
# NetAtmo Data is uploaded to server every 10mn
# so this time should not be under
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=600)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the available NetAtmo weather sensors."""
    netatmo = get_component('netatmo')
    data = NetAtmoData(authorization, config.get(CONF_STATION, None))

    dev = []
    try:
        # Iterate each module
        for module_name, monitored_conditions in config[ATTR_MODULE].items():
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
                        NetAtmoSensor(data, module_name, variable))
    except KeyError:
        pass

    add_devices(dev)


# pylint: disable=too-few-public-methods
class NetAtmoSensor(Entity):
    """Implementation of a NetAtmo sensor."""

    def __init__(self, netatmo_data, module_name, sensor_type):
        """Initialize the sensor."""
        self._name = "NetAtmo {} {}".format(module_name,
                                            SENSOR_TYPES[sensor_type][0])
        self.netatmo_data = netatmo_data
        self.module_name = module_name
        self.type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return SENSOR_TYPES[self.type][2]

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    # pylint: disable=too-many-branches
    def update(self):
        """Get the latest data from NetAtmo API and updates the states."""
        self.netatmo_data.update()
        data = self.netatmo_data.data[self.module_name]

        if self.type == 'temperature':
            self._state = round(data['Temperature'], 1)
        elif self.type == 'humidity':
            self._state = data['Humidity']
        elif self.type == 'rain':
            self._state = data['Rain']
        elif self.type == 'sum_rain_1':
            self._state = data['sum_rain_1']
        elif self.type == 'sum_rain_24':
            self._state = data['sum_rain_24']
        elif self.type == 'noise':
            self._state = data['Noise']
        elif self.type == 'co2':
            self._state = data['CO2']
        elif self.type == 'pressure':
            self._state = round(data['Pressure'], 1)


class NetAtmoData(object):
    """Get the latest data from NetAtmo."""

    def __init__(self, auth, station):
        """Initialize the data object."""
        self.auth = auth
        self.data = None
        self.station = station

    def get_module_names(self):
        """Return all module available on the API as a list."""
        self.update()
        return self.data.keys()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Call the NetAtmo API to update the data."""
        import lnetatmo
        dev_list = lnetatmo.DeviceList(self.auth)

        if self.station is not None:
            self.data = dev_list.lastData(station=self.station, exclude=3600)
        else:
            self.data = dev_list.lastData(exclude=3600)
