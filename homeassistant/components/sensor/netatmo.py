"""
Support for the NetAtmo Weather Service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.netatmo/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.loader import get_component
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTR_MODULE = 'modules'

CONF_MODULES = 'modules'
CONF_STATION = 'station'

DEPENDENCIES = ['netatmo']

# NetAtmo Data is uploaded to server every 10 minutes
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=600)

SENSOR_TYPES = {
    'temperature': ['Temperature', TEMP_CELSIUS, 'mdi:thermometer'],
    'co2': ['CO2', 'ppm', 'mdi:cloud'],
    'pressure': ['Pressure', 'mbar', 'mdi:gauge'],
    'noise': ['Noise', 'dB', 'mdi:volume-high'],
    'humidity': ['Humidity', '%', 'mdi:water-percent'],
    'rain': ['Rain', 'mm', 'mdi:weather-rainy'],
    'sum_rain_1': ['sum_rain_1', 'mm', 'mdi:weather-rainy'],
    'sum_rain_24': ['sum_rain_24', 'mm', 'mdi:weather-rainy'],
    'battery_vp': ['Battery', '', 'mdi:battery'],
    'min_temp': ['Min Temp.', TEMP_CELSIUS, 'mdi:thermometer'],
    'max_temp': ['Max Temp.', TEMP_CELSIUS, 'mdi:thermometer'],
    'WindAngle': ['Angle', '', 'mdi:compass'],
    'WindStrength': ['Strength', 'km/h', 'mdi:weather-windy'],
    'GustAngle': ['Gust Angle', '', 'mdi:compass'],
    'GustStrength': ['Gust Strength', 'km/h', 'mdi:weather-windy'],
    'rf_status': ['Radio', '', 'mdi:signal'],
    'wifi_status': ['Wifi', '', 'mdi:wifi']
}

MODULE_SCHEMA = vol.Schema({
    vol.Required(cv.string, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_STATION): cv.string,
    vol.Required(CONF_MODULES): MODULE_SCHEMA,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the available Netatmo weather sensors."""
    netatmo = get_component('netatmo')
    data = NetAtmoData(netatmo.NETATMO_AUTH, config.get(CONF_STATION, None))

    dev = []
    try:
        # Iterate each module
        for module_name, monitored_conditions in config[CONF_MODULES].items():
            # Test if module exist """
            if module_name not in data.get_module_names():
                _LOGGER.error('Module name: "%s" not found', module_name)
                continue
            # Only create sensor for monitored """
            for variable in monitored_conditions:
                dev.append(NetAtmoSensor(data, module_name, variable))
    except KeyError:
        pass

    add_devices(dev)


# pylint: disable=too-few-public-methods
class NetAtmoSensor(Entity):
    """Implementation of a Netatmo sensor."""

    def __init__(self, netatmo_data, module_name, sensor_type):
        """Initialize the sensor."""
        self._name = 'Netatmo {} {}'.format(module_name,
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
    # Fix for pylint too many statements error
    # pylint: disable=too-many-statements
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
        elif self.type == 'battery_vp':
            if data['battery_vp'] >= 5500:
                self._state = "Full"
            elif data['battery_vp'] >= 5100:
                self._state = "High"
            elif data['battery_vp'] >= 4600:
                self._state = "Medium"
            elif data['battery_vp'] >= 4100:
                self._state = "Low"
            elif data['battery_vp'] < 4100:
                self._state = "Very Low"
        elif self.type == 'min_temp':
            self._state = data['min_temp']
        elif self.type == 'max_temp':
            self._state = data['max_temp']
        elif self.type == 'WindAngle':
            if data['WindAngle'] >= 330:
                self._state = "North (%d\xb0)" % data['WindAngle']
            elif data['WindAngle'] >= 300:
                self._state = "North-West (%d\xb0)" % data['WindAngle']
            elif data['WindAngle'] >= 240:
                self._state = "West (%d\xb0)" % data['WindAngle']
            elif data['WindAngle'] >= 210:
                self._state = "South-West (%d\xb0)" % data['WindAngle']
            elif data['WindAngle'] >= 150:
                self._state = "South (%d\xb0)" % data['WindAngle']
            elif data['WindAngle'] >= 120:
                self._state = "South-East (%d\xb0)" % data['WindAngle']
            elif data['WindAngle'] >= 60:
                self._state = "East (%d\xb0)" % data['WindAngle']
            elif data['WindAngle'] >= 30:
                self._state = "North-East (%d\xb0)" % data['WindAngle']
            elif data['WindAngle'] >= 0:
                self._state = "North (%d\xb0)" % data['WindAngle']
        elif self.type == 'WindStrength':
            self._state = data['WindStrength']
        elif self.type == 'GustAngle':
            if data['GustAngle'] >= 330:
                self._state = "North (%d\xb0)" % data['GustAngle']
            elif data['GustAngle'] >= 300:
                self._state = "North-West (%d\xb0)" % data['GustAngle']
            elif data['GustAngle'] >= 240:
                self._state = "West (%d\xb0)" % data['GustAngle']
            elif data['GustAngle'] >= 210:
                self._state = "South-West (%d\xb0)" % data['GustAngle']
            elif data['GustAngle'] >= 150:
                self._state = "South (%d\xb0)" % data['GustAngle']
            elif data['GustAngle'] >= 120:
                self._state = "South-East (%d\xb0)" % data['GustAngle']
            elif data['GustAngle'] >= 60:
                self._state = "East (%d\xb0)" % data['GustAngle']
            elif data['GustAngle'] >= 30:
                self._state = "North-East (%d\xb0)" % data['GustAngle']
            elif data['GustAngle'] >= 0:
                self._state = "North (%d\xb0)" % data['GustAngle']
        elif self.type == 'GustStrength':
            self._state = data['GustStrength']
        elif self.type == 'rf_status':
            if data['rf_status'] >= 90:
                self._state = "Low"
            elif data['rf_status'] >= 76:
                self._state = "Medium"
            elif data['rf_status'] >= 60:
                self._state = "High"
            elif data['rf_status'] <= 59:
                self._state = "Full"
        elif self.type == 'wifi_status':
            if data['wifi_status'] >= 86:
                self._state = "Bad"
            elif data['wifi_status'] >= 71:
                self._state = "Middle"
            elif data['wifi_status'] <= 70:
                self._state = "Good"


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
        """Call the Netatmo API to update the data."""
        import lnetatmo
        dev_list = lnetatmo.DeviceList(self.auth)

        if self.station is not None:
            self.data = dev_list.lastData(station=self.station, exclude=3600)
        else:
            self.data = dev_list.lastData(exclude=3600)
