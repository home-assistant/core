"""
Support for Sensors using public Netatmo data.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.netatmo_public/.
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME, CONF_TYPE)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['netatmo']

CONF_AREAS = 'areas'
CONF_LAT_NE = 'lat_ne'
CONF_LON_NE = 'lon_ne'
CONF_LAT_SW = 'lat_sw'
CONF_LON_SW = 'lon_sw'

DEFAULT_NAME = 'Netatmo Public Data'
DEFAULT_TYPE = 'max'
SENSOR_TYPES = {'max', 'avg'}

# NetAtmo Data is uploaded to server every 10 minutes
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=600)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_AREAS): vol.All(cv.ensure_list, [
        {
            vol.Required(CONF_LAT_NE): cv.latitude,
            vol.Required(CONF_LAT_SW): cv.latitude,
            vol.Required(CONF_LON_NE): cv.longitude,
            vol.Required(CONF_LON_SW): cv.longitude,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_TYPE, default=DEFAULT_TYPE):
                vol.In(SENSOR_TYPES)
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
                                 lon_sw=area_conf.get(CONF_LON_SW),
                                 calculation=area_conf.get(CONF_TYPE))
        sensors.append(NetatmoPublicSensor(area_conf.get(CONF_NAME), data))
    add_entities(sensors)


class NetatmoPublicSensor(Entity):
    """Represent a single sensor in a Netatmo."""

    def __init__(self, name, data):
        """Initialize the sensor."""
        self.netatmo_data = data
        self._name = name
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return 'mdi:weather-rainy'

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return None

    @property
    def state(self):
        """Return true if binary sensor is on."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return 'mm'

    def update(self):
        """Get the latest data from NetAtmo API and updates the states."""
        self.netatmo_data.update()
        self._state = self.netatmo_data.data


class NetatmoPublicData:
    """Get the latest data from NetAtmo."""

    def __init__(self, auth, lat_ne, lon_ne, lat_sw, lon_sw, calculation):
        """Initialize the data object."""
        self.auth = auth
        self.data = None
        self.lat_ne = lat_ne
        self.lon_ne = lon_ne
        self.lat_sw = lat_sw
        self.lon_sw = lon_sw
        self.calculation = calculation

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Request an update from the Netatmo API."""
        import pyatmo
        raindata = pyatmo.PublicData(self.auth,
                                     LAT_NE=self.lat_ne,
                                     LON_NE=self.lon_ne,
                                     LAT_SW=self.lat_sw,
                                     LON_SW=self.lon_sw,
                                     required_data_type="rain")

        if raindata.CountStationInArea() == 0:
            _LOGGER.warning('No Rain Station available in this area.')
            return

        raindata_live = raindata.getLive()

        if self.calculation == 'avg':
            self.data = sum(raindata_live.values()) / len(raindata_live)
        else:
            self.data = max(raindata_live.values())
