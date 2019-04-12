"""Support for the NetAtmo Weather Service."""
import logging
from time import time
import threading

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    TEMP_CELSIUS, DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_BATTERY)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

from . import NETATMO_AUTH

_LOGGER = logging.getLogger(__name__)

CONF_MODULES = 'modules'
CONF_STATION = 'station'

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
    'battery_percent': ['battery_percent', '%', None, DEVICE_CLASS_BATTERY],
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
    'health_idx': ['Health', '', 'mdi:cloud', None],
}

MODULE_SCHEMA = vol.Schema({
    vol.Required(cv.string): vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_STATION): cv.string,
    vol.Optional(CONF_MODULES): MODULE_SCHEMA,
})

MODULE_TYPE_OUTDOOR = 'NAModule1'
MODULE_TYPE_WIND = 'NAModule2'
MODULE_TYPE_RAIN = 'NAModule3'
MODULE_TYPE_INDOOR = 'NAModule4'


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the available Netatmo weather sensors."""
    dev = []
    if CONF_MODULES in config:
        manual_config(config, dev)
    else:
        auto_config(config, dev)

    if dev:
        add_entities(dev, True)


def manual_config(config, dev):
    """Handle manual configuration."""
    import pyatmo

    all_classes = all_product_classes()
    not_handled = {}
    for data_class in all_classes:
        data = NetAtmoData(NETATMO_AUTH, data_class,
                           config.get(CONF_STATION))
        try:
            # Iterate each module
            for module_name, monitored_conditions in \
                    config[CONF_MODULES].items():
                # Test if module exists
                if module_name not in data.get_module_names():
                    not_handled[module_name] = \
                        not_handled[module_name]+1 \
                        if module_name in not_handled else 1
                else:
                    # Only create sensors for monitored properties
                    for variable in monitored_conditions:
                        dev.append(NetAtmoSensor(data, module_name, variable))
        except pyatmo.NoDevice:
            continue

    for module_name, count in not_handled.items():
        if count == len(all_classes):
            _LOGGER.error('Module name: "%s" not found', module_name)


def auto_config(config, dev):
    """Handle auto configuration."""
    import pyatmo

    for data_class in all_product_classes():
        data = NetAtmoData(NETATMO_AUTH, data_class, config.get(CONF_STATION))
        try:
            for module_name in data.get_module_names():
                for variable in \
                        data.station_data.monitoredConditions(module_name):
                    if variable in SENSOR_TYPES.keys():
                        dev.append(NetAtmoSensor(data, module_name, variable))
                    else:
                        _LOGGER.warning("Ignoring unknown var %s for mod %s",
                                        variable, module_name)
        except pyatmo.NoDevice:
            continue


def all_product_classes():
    """Provide all handled Netatmo product classes."""
    import pyatmo

    return [pyatmo.WeatherStationData, pyatmo.HomeCoachData]


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
        self._module_type = self.netatmo_data. \
            station_data.moduleByName(module=module_name)['type']
        module_id = self.netatmo_data. \
            station_data.moduleByName(module=module_name)['_id']
        self._unique_id = '{}-{}'.format(module_id, self.type)

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

    @property
    def unique_id(self):
        """Return the unique ID for this sensor."""
        return self._unique_id

    def update(self):
        """Get the latest data from NetAtmo API and updates the states."""
        self.netatmo_data.update()
        if self.netatmo_data.data is None:
            if self._state is None:
                return
            _LOGGER.warning("No data found for %s", self.module_name)
            self._state = None
            return

        data = self.netatmo_data.data.get(self.module_name)

        if data is None:
            _LOGGER.warning("No data found for %s", self.module_name)
            self._state = None
            return

        try:
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
            elif self.type == 'battery_percent':
                self._state = data['battery_percent']
            elif self.type == 'battery_lvl':
                self._state = data['battery_vp']
            elif (self.type == 'battery_vp' and
                  self._module_type == MODULE_TYPE_WIND):
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
            elif (self.type == 'battery_vp' and
                  self._module_type == MODULE_TYPE_RAIN):
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
            elif (self.type == 'battery_vp' and
                  self._module_type == MODULE_TYPE_INDOOR):
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
            elif (self.type == 'battery_vp' and
                  self._module_type == MODULE_TYPE_OUTDOOR):
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
            elif self.type == 'health_idx':
                if data['health_idx'] == 0:
                    self._state = "Healthy"
                elif data['health_idx'] == 1:
                    self._state = "Fine"
                elif data['health_idx'] == 2:
                    self._state = "Fair"
                elif data['health_idx'] == 3:
                    self._state = "Poor"
                elif data['health_idx'] == 4:
                    self._state = "Unhealthy"
        except KeyError:
            _LOGGER.error("No %s data found for %s", self.type,
                          self.module_name)
            self._state = None
            return


class NetAtmoData:
    """Get the latest data from NetAtmo."""

    def __init__(self, auth, data_class, station):
        """Initialize the data object."""
        self.auth = auth
        self.data_class = data_class
        self.data = None
        self.station_data = None
        self.station = station
        self._next_update = time()
        self._update_in_progress = threading.Lock()

    def get_module_names(self):
        """Return all module available on the API as a list."""
        self.update()
        if not self.data:
            return []
        return self.data.keys()

    def _detect_platform_type(self):
        """Return the XXXData object corresponding to the specified platform.

        The return can be a WeatherStationData or a HomeCoachData.
        """
        try:
            station_data = self.data_class(self.auth)
            _LOGGER.debug("%s detected!", str(self.data_class.__name__))
            return station_data
        except TypeError:
            return

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
            self.station_data = self._detect_platform_type()
            if not self.station_data:
                raise Exception("No Weather nor HomeCoach devices found")

            if self.station is not None:
                self.data = self.station_data.lastData(
                    station=self.station, exclude=3600)
            else:
                self.data = self.station_data.lastData(exclude=3600)

            newinterval = 0
            try:
                for module in self.data:
                    if 'When' in self.data[module]:
                        newinterval = self.data[module]['When']
                        break
            except TypeError:
                _LOGGER.debug("No %s modules found", self.data_class.__name__)

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
                    _LOGGER.info(
                        "NetAtmo refresh interval reset to %d seconds",
                        newinterval)
            else:
                # Last update time not found, fall back to default value
                newinterval = NETATMO_UPDATE_INTERVAL

            self._next_update = time() + newinterval
        finally:
            self._update_in_progress.release()
