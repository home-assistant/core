"""
Support for the CO2signal platform.

For more details about this platform, please refer to the documentation
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_TOKEN, CONF_LATITUDE, CONF_LONGITUDE)
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity

CONF_COUNTRY_CODE = "country_code"

REQUIREMENTS = ['co2signal==0.4.2']

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = 'Data provided by CO2signal'

MSG_LOCATION = "Please use either coordinates or the country code. " \
               "For the coordinates, " \
               "you need to use both latitude and longitude."
CO2_INTENSITY_UNIT = "CO2eq/kWh"
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TOKEN): cv.string,
    vol.Inclusive(CONF_LATITUDE, 'coords', msg=MSG_LOCATION): cv.latitude,
    vol.Inclusive(CONF_LONGITUDE, 'coords', msg=MSG_LOCATION): cv.longitude,
    vol.Optional(CONF_COUNTRY_CODE): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the CO2signal sensor."""
    token = config[CONF_TOKEN]
    lat = config.get(CONF_LATITUDE, hass.config.latitude)
    lon = config.get(CONF_LONGITUDE, hass.config.longitude)
    country_code = config.get(CONF_COUNTRY_CODE)

    _LOGGER.debug("Setting up the sensor using the %s", country_code)

    devs = []

    devs.append(CO2Sensor(token,
                          country_code,
                          lat,
                          lon))
    add_entities(devs, True)


class CO2Sensor(Entity):
    """Implementation of the CO2Signal sensor."""

    def __init__(self, token, country_code, lat, lon):
        """Initialize the sensor."""
        self._token = token
        self._country_code = country_code
        self._latitude = lat
        self._longitude = lon
        self._data = None

        if country_code is not None:
            device_name = country_code
        else:
            device_name = '{lat}/{lon}'\
                .format(lat=round(self._latitude, 2),
                        lon=round(self._longitude, 2))

        self._friendly_name = 'CO2 intensity - {}'.format(device_name)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._friendly_name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return 'mdi:periodic-table-co2'

    @property
    def state(self):
        """Return the state of the device."""
        return self._data

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return CO2_INTENSITY_UNIT

    @property
    def device_state_attributes(self):
        """Return the state attributes of the last update."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}

    def update(self):
        """Get the latest data and updates the states."""
        import CO2Signal

        _LOGGER.debug("Update data for %s", self._friendly_name)

        if self._country_code is not None:
            self._data = CO2Signal.get_latest_carbon_intensity(
                self._token, country_code=self._country_code)
        else:
            self._data = CO2Signal.get_latest_carbon_intensity(
                self._token,
                latitude=self._latitude, longitude=self._longitude)

        self._data = round(self._data, 2)
