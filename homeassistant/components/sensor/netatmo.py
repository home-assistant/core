"""
Support for the NetAtmo Weather Service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.netatmo/
"""
import logging
from time import time
import threading

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    TEMP_CELSIUS, DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_TEMPERATURE,
    STATE_UNKNOWN)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_MODULES = 'modules'
CONF_STATION = 'station'

DEPENDENCIES = ['netatmo']

# This is the NetAtmo data upload interval in seconds
NETATMO_UPDATE_INTERVAL = 600

SENSOR_TYPES = {
    'temperature': ['Temperature', TEMP_CELSIUS, None,
                    DEVICE_CLASS_TEMPERATURE],
    'co2': ['CO2', 'ppm', 'mdi:cloud', None],
    'pressure': ['Pressure', 'mbar', 'mdi:gauge', None],
    'noise': ['Noise', 'dB', 'mdi:volume-high', None],
    'humidity': ['Humidity', '%', None, DEVICE_CLASS_HUMIDITY],
    'rain': ['Rain', 'mm', 'mdi:weather-rainy', None],
    'sum_rain_1': ['sum_rain_1', 'mm', 'mdi:weather-rainy', None],
    'sum_rain_24': ['sum_rain_24', 'mm', 'mdi:weather-rainy', None],
    'battery_vp': ['Battery', '', 'mdi:battery', None],
    'battery_lvl': ['Battery_lvl', '', 'mdi:battery', None],
    'min_temp': ['Min Temp.', TEMP_CELSIUS, 'mdi:thermometer', None],
    'max_temp': ['Max Temp.', TEMP_CELSIUS, 'mdi:thermometer', None],
    'windangle': ['Angle', '', 'mdi:compass', None],
    'windangle_value': ['Angle Value', 'º', 'mdi:compass', None],
    'windstrength': ['Strength', 'km/h', 'mdi:weather-windy', None],
    'gustangle': ['Gust Angle', '', 'mdi:compass', None],
    'gustangle_value': ['Gust Angle Value', 'º', 'mdi:compass', None],
    'guststrength': ['Gust Strength', 'km/h', 'mdi:weather-windy', None],
    'rf_status': ['Radio', '', 'mdi:signal', None],
    'rf_status_lvl': ['Radio_lvl', '', 'mdi:signal', None],
    'wifi_status': ['Wifi', '', 'mdi:wifi', None],
    'wifi_status_lvl': ['Wifi_lvl', 'dBm', 'mdi:wifi', None],
}

MODULE_SCHEMA = vol.Schema({
    vol.Required(cv.string):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_STATION): cv.string,
    vol.Optional(CONF_MODULES): MODULE_SCHEMA,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the available Netatmo weather sensors."""
    netatmo = hass.components.netatmo
    data = NetAtmoData(netatmo.NETATMO_AUTH, config.get(CONF_STATION, None))

    dev = []
    import pyatmo
    try:
        if CONF_MODULES in config:
            # Iterate each module
            for module_name, monitored_conditions in\
                    config[CONF_MODULES].items():
                # Test if module exists
                if module_name not in data.get_module_names():
                    _LOGGER.error('Module name: "%s" not found', module_name)
                    continue
                # Only create sensors for monitored properties
                for variable in monitored_conditions:
                    dev.append(NetAtmoSensor(data, module_name, variable))
        else:
            for module_name in data.get_module_names():
                for variable in\
                        data.station_data.monitoredConditions(module_name):
                    if variable in SENSOR_TYPES.keys():
                        dev.append(NetAtmoSensor(data, module_name, variable))
                    else:
                        _LOGGER.warning("Ignoring unknown var %s for mod %s",
                                        variable, module_name)
    except pyatmo.NoDevice:
        return None

    add_devices(dev, True)


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
        self._device_class = SENSOR_TYPES[self.type][3]
        self._icon = SENSOR_TYPES[self.type][2]
        self._unit_of_measurement = SENSOR_TYPES[self.type][1]
        module_id = self.netatmo_data.\
            station_data.moduleByName(module=module_name)['_id']
        self.module_id = module_id[1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest data from NetAtmo API and updates the states."""
        self.netatmo_data.update()
        data = self.netatmo_data.data.get(self.module_name)

        if data is None:
            _LOGGER.warning("No data found for %s", self.module_name)
            self._state = STATE_UNKNOWN
            return

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
        elif self.type == 'battery_lvl':
            self._state = data['battery_vp']
        elif self.type == 'battery_vp' and self.module_id == '6':
            if data['battery_vp'] >= 5590:
                self._state = "Full"
            elif data['battery_vp'] >= 5180:
                self._state = "High"
            elif data['battery_vp'] >= 4770:
                self._state = "Medium"
            elif data['battery_vp'] >= 4360:
                self._state = "Low"
            elif data['battery_vp'] < 4360:
                self._state = "Very Low"
        elif self.type == 'battery_vp' and self.module_id == '5':
            if data['battery_vp'] >= 5500:
                self._state = "Full"
            elif data['battery_vp'] >= 5000:
                self._state = "High"
            elif data['battery_vp'] >= 4500:
                self._state = "Medium"
            elif data['battery_vp'] >= 4000:
                self._state = "Low"
            elif data['battery_vp'] < 4000:
                self._state = "Very Low"
        elif self.type == 'battery_vp' and self.module_id == '3':
            if data['battery_vp'] >= 5640:
                self._state = "Full"
            elif data['battery_vp'] >= 5280:
                self._state = "High"
            elif data['battery_vp'] >= 4920:
                self._state = "Medium"
            elif data['battery_vp'] >= 4560:
                self._state = "Low"
            elif data['battery_vp'] < 4560:
                self._state = "Very Low"
        elif self.type == 'battery_vp' and self.module_id == '2':
            if data['battery_vp'] >= 5500:
                self._state = "Full"
            elif data['battery_vp'] >= 5000:
                self._state = "High"
            elif data['battery_vp'] >= 4500:
                self._state = "Medium"
            elif data['battery_vp'] >= 4000:
                self._state = "Low"
            elif data['battery_vp'] < 4000:
                self._state = "Very Low"
        elif self.type == 'min_temp':
            self._state = data['min_temp']
        elif self.type == 'max_temp':
            self._state = data['max_temp']
        elif self.type == 'windangle_value':
            self._state = data['WindAngle']
        elif self.type == 'windangle':
            if data['WindAngle'] >= 330:
                self._state = "N (%d\xb0)" % data['WindAngle']
            elif data['WindAngle'] >= 300:
                self._state = "NW (%d\xb0)" % data['WindAngle']
            elif data['WindAngle'] >= 240:
                self._state = "W (%d\xb0)" % data['WindAngle']
            elif data['WindAngle'] >= 210:
                self._state = "SW (%d\xb0)" % data['WindAngle']
            elif data['WindAngle'] >= 150:
                self._state = "S (%d\xb0)" % data['WindAngle']
            elif data['WindAngle'] >= 120:
                self._state = "SE (%d\xb0)" % data['WindAngle']
            elif data['WindAngle'] >= 60:
                self._state = "E (%d\xb0)" % data['WindAngle']
            elif data['WindAngle'] >= 30:
                self._state = "NE (%d\xb0)" % data['WindAngle']
            elif data['WindAngle'] >= 0:
                self._state = "N (%d\xb0)" % data['WindAngle']
        elif self.type == 'windstrength':
            self._state = data['WindStrength']
        elif self.type == 'gustangle_value':
            self._state = data['GustAngle']
        elif self.type == 'gustangle':
            if data['GustAngle'] >= 330:
                self._state = "N (%d\xb0)" % data['GustAngle']
            elif data['GustAngle'] >= 300:
                self._state = "NW (%d\xb0)" % data['GustAngle']
            elif data['GustAngle'] >= 240:
                self._state = "W (%d\xb0)" % data['GustAngle']
            elif data['GustAngle'] >= 210:
                self._state = "SW (%d\xb0)" % data['GustAngle']
            elif data['GustAngle'] >= 150:
                self._state = "S (%d\xb0)" % data['GustAngle']
            elif data['GustAngle'] >= 120:
                self._state = "SE (%d\xb0)" % data['GustAngle']
            elif data['GustAngle'] >= 60:
                self._state = "E (%d\xb0)" % data['GustAngle']
            elif data['GustAngle'] >= 30:
                self._state = "NE (%d\xb0)" % data['GustAngle']
            elif data['GustAngle'] >= 0:
                self._state = "N (%d\xb0)" % data['GustAngle']
        elif self.type == 'guststrength':
            self._state = data['GustStrength']
        elif self.type == 'rf_status_lvl':
            self._state = data['rf_status']
        elif self.type == 'rf_status':
            if data['rf_status'] >= 90:
                self._state = "Low"
            elif data['rf_status'] >= 76:
                self._state = "Medium"
            elif data['rf_status'] >= 60:
                self._state = "High"
            elif data['rf_status'] <= 59:
                self._state = "Full"
        elif self.type == 'wifi_status_lvl':
            self._state = data['wifi_status']
        elif self.type == 'wifi_status':
            if data['wifi_status'] >= 86:
                self._state = "Low"
            elif data['wifi_status'] >= 71:
                self._state = "Medium"
            elif data['wifi_status'] >= 56:
                self._state = "High"
            elif data['wifi_status'] <= 55:
                self._state = "Full"


class NetAtmoData(object):
    """Get the latest data from NetAtmo."""

    def __init__(self, auth, station):
        """Initialize the data object."""
        self.auth = auth
        self.data = None
        self.station_data = None
        self.station = station
        self._next_update = time()
        self._update_in_progress = threading.Lock()

    def get_module_names(self):
        """Return all module available on the API as a list."""
        self.update()
        return self.data.keys()

    def update(self):
        """Call the Netatmo API to update the data.

        This method is not throttled by the builtin Throttle decorator
        but with a custom logic, which takes into account the time
        of the last update from the cloud.
        """
        if time() < self._next_update or \
                not self._update_in_progress.acquire(False):
            return

        try:
            import pyatmo
            self.station_data = pyatmo.WeatherStationData(self.auth)

            if self.station is not None:
                self.data = self.station_data.lastData(
                    station=self.station, exclude=3600)
            else:
                self.data = self.station_data.lastData(exclude=3600)

            newinterval = 0
            for module in self.data:
                if 'When' in self.data[module]:
                    newinterval = self.data[module]['When']
                    break
            if newinterval:
                # Try and estimate when fresh data will be available
                newinterval += NETATMO_UPDATE_INTERVAL - time()
                if newinterval > NETATMO_UPDATE_INTERVAL - 30:
                    newinterval = NETATMO_UPDATE_INTERVAL
                else:
                    if newinterval < NETATMO_UPDATE_INTERVAL / 2:
                        # Never hammer the NetAtmo API more than
                        # twice per update interval
                        newinterval = NETATMO_UPDATE_INTERVAL / 2
                    _LOGGER.warning(
                        "NetAtmo refresh interval reset to %d seconds",
                        newinterval)
            else:
                # Last update time not found, fall back to default value
                newinterval = NETATMO_UPDATE_INTERVAL

            self._next_update = time() + newinterval
        finally:
            self._update_in_progress.release()
