"""Support for Sensors using public Netatmo data."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_MODE, CONF_MONITORED_CONDITIONS, TEMP_CELSIUS,
    DEVICE_CLASS_TEMPERATURE, DEVICE_CLASS_HUMIDITY)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

CONF_AREAS = 'areas'
CONF_LAT_NE = 'lat_ne'
CONF_LON_NE = 'lon_ne'
CONF_LAT_SW = 'lat_sw'
CONF_LON_SW = 'lon_sw'

DEFAULT_NAME = 'Netatmo Public Data'
DEFAULT_MODE = 'avg'
MODE_TYPES = {'max', 'avg'}

SENSOR_TYPES = {
    'temperature': ['Temperature', TEMP_CELSIUS, 'mdi:thermometer',
                    DEVICE_CLASS_TEMPERATURE],
    'pressure': ['Pressure', 'mbar', 'mdi:gauge', None],
    'humidity': ['Humidity', '%', 'mdi:water-percent', DEVICE_CLASS_HUMIDITY],
    'rain': ['Rain', 'mm', 'mdi:weather-rainy', None],
    'windstrength': ['Wind Strength', 'km/h', 'mdi:weather-windy', None],
    'guststrength': ['Gust Strength', 'km/h', 'mdi:weather-windy', None],
}

# NetAtmo Data is uploaded to server every 10 minutes
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=600)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_AREAS): vol.All(cv.ensure_list, [
        {
            vol.Required(CONF_LAT_NE): cv.latitude,
            vol.Required(CONF_LAT_SW): cv.latitude,
            vol.Required(CONF_LON_NE): cv.longitude,
            vol.Required(CONF_LON_SW): cv.longitude,
            vol.Required(CONF_MONITORED_CONDITIONS): [vol.In(SENSOR_TYPES)],
            vol.Optional(CONF_MODE, default=DEFAULT_MODE): vol.In(MODE_TYPES),
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
        }
    ]),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the access to Netatmo binary sensor."""
    netatmo = hass.components.netatmo

    sensors = []
    areas = config.get(CONF_AREAS)
    for area_conf in areas:
        data = NetatmoPublicData(netatmo.NETATMO_AUTH,
                                 lat_ne=area_conf.get(CONF_LAT_NE),
                                 lon_ne=area_conf.get(CONF_LON_NE),
                                 lat_sw=area_conf.get(CONF_LAT_SW),
                                 lon_sw=area_conf.get(CONF_LON_SW))
        for sensor_type in area_conf.get(CONF_MONITORED_CONDITIONS):
            sensors.append(NetatmoPublicSensor(area_conf.get(CONF_NAME),
                                               data, sensor_type,
                                               area_conf.get(CONF_MODE)))
    add_entities(sensors, True)


class NetatmoPublicSensor(Entity):
    """Represent a single sensor in a Netatmo."""

    def __init__(self, area_name, data, sensor_type, mode):
        """Initialize the sensor."""
        self.netatmo_data = data
        self.type = sensor_type
        self._mode = mode
        self._name = '{} {}'.format(area_name,
                                    SENSOR_TYPES[self.type][0])
        self._area_name = area_name
        self._state = None
        self._device_class = SENSOR_TYPES[self.type][3]
        self._icon = SENSOR_TYPES[self.type][2]
        self._unit_of_measurement = SENSOR_TYPES[self.type][1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend."""
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
        """Return the unit of measurement of this entity."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest data from NetAtmo API and updates the states."""
        self.netatmo_data.update()

        if self.netatmo_data.data is None:
            _LOGGER.warning("No data found for %s", self._name)
            self._state = None
            return

        data = None

        if self.type == 'temperature':
            data = self.netatmo_data.data.getLatestTemperatures()
        elif self.type == 'pressure':
            data = self.netatmo_data.data.getLatestPressures()
        elif self.type == 'humidity':
            data = self.netatmo_data.data.getLatestHumidities()
        elif self.type == 'rain':
            data = self.netatmo_data.data.getLatestRain()
        elif self.type == 'windstrength':
            data = self.netatmo_data.data.getLatestWindStrengths()
        elif self.type == 'guststrength':
            data = self.netatmo_data.data.getLatestGustStrengths()

        if not data:
            _LOGGER.warning("No station provides %s data in the area %s",
                            self.type, self._area_name)
            self._state = None
            return

        if self._mode == 'avg':
            self._state = round(sum(data.values()) / len(data), 1)
        elif self._mode == 'max':
            self._state = max(data.values())


class NetatmoPublicData:
    """Get the latest data from NetAtmo."""

    def __init__(self, auth, lat_ne, lon_ne, lat_sw, lon_sw):
        """Initialize the data object."""
        self.auth = auth
        self.data = None
        self.lat_ne = lat_ne
        self.lon_ne = lon_ne
        self.lat_sw = lat_sw
        self.lon_sw = lon_sw

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Request an update from the Netatmo API."""
        import pyatmo
        data = pyatmo.PublicData(self.auth,
                                 LAT_NE=self.lat_ne,
                                 LON_NE=self.lon_ne,
                                 LAT_SW=self.lat_sw,
                                 LON_SW=self.lon_sw,
                                 filtering=True)

        if data.CountStationInArea() == 0:
            _LOGGER.warning('No Stations available in this area.')
            return

        self.data = data
