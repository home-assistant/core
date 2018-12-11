"""
Support for the CO2signal platform.
For more details about this platform, please refer to the documentation
"""
import logging
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    ATTR_ATTRIBUTION, ATTR_TIME, ATTR_TEMPERATURE, CONF_TOKEN, CONF_LATITUDE, CONF_LONGITUDE)
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity

CONF_REFRESH = "refresh_rate"
CONF_COUNTRY_CODE = "country_code"

REQUIREMENTS = ['co2signal==0.2']

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = 'Data provided by CO2signal'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_TOKEN, default = None): cv.string,
    vol.Optional(CONF_COUNTRY_CODE, default = None): cv.string,
    vol.Optional(CONF_LATITUDE, default = 0): cv.latitude,
    vol.Optional(CONF_LONGITUDE, default = 0): cv.longitude,
    vol.Optional(CONF_REFRESH, default = 60): cv.positive_int,
})

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the CO2signal sensor."""

    _LOGGER.debug("Setting up the CO2signal platform")

    token = config.get(CONF_TOKEN)
    country_code = config.get(CONF_COUNTRY_CODE)
    refresh_rate = config.get(CONF_REFRESH)
    lat = None
    lon = None
    location_type = None

    # find station ID
    if country_code is not None:
        location_type = 'country_code'
    else:
        lat = config.get(CONF_LATITUDE)
        lon = config.get(CONF_LONGITUDE)
        location_type = 'coordinates'

    _LOGGER.debug("Setting up the sensor using the %s", location_type)

    devs = []

    devs.append(CO2Sensor(token, country_code, lat, lon, location_type, refresh_rate))

    add_devices(devs)


class CO2Sensor(Entity):
    """Implementation of the CO2Signal sensor."""

    _friendly_name: str

    def __init__(self, token, country_code, lat, lon, location_type, refresh_rate = 15):
        """Initialize the sensor."""
        import CO2Signal

        self._token = token
        self._country_code = country_code
        self._latitude = lat
        self._longitude = lon
        self._location_type = location_type
        self._unit = 'CO2eq/kWh'
        self._device_name = "LatLon"
        if country_code is not None:
            self._device_name = country_code
        self._friendly_name = 'CO2 intensity - {}'.format(self._device_name)
        self._refresh_rate = refresh_rate

        _LOGGER.debug("Initialise %s", self._friendly_name)

        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._friendly_name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return 'mdi:periodic-table-co2'

    @property
    def device_class(self):
        """Return the device class."""
        """Icon to use in the frontend, if any."""
        return 'carbon_dioxide_intensity'

    @property
    def state(self):
        import datetime
        """Return the state of the device."""
        _LOGGER.debug("Get state for %s", self._friendly_name)
        return self._data

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit

    def update(self):
        """Get the latest data and updates the states."""
        import CO2Signal

        _LOGGER.debug("Update data for %s", self._friendly_name)

        if self._location_type == 'country_code':
            self._data = CO2Signal.get_latest_carbon_intensity(self._token, country_code = self._country_code)
        elif self._location_type == 'coordinates':
            self._data = CO2Signal.get_latest_carbon_intensity(self._token, latitude = self._latitude, longitude = self._longitude)
        else:
            raise ValueError("Unknown location type: {location_type}".format(location_type = self._location_type))