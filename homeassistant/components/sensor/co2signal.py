"""
Support for the CO2signal platform.
For more details about this platform, please refer to the documentation
"""
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.const import (
    CONF_TOKEN, CONF_LATITUDE, CONF_LONGITUDE)
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity

CONF_COUNTRY_CODE = "country_code"

REQUIREMENTS = ['co2signal==0.4.1']

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = 'Data provided by CO2signal'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TOKEN): cv.string,
    vol.Inclusive(CONF_LATITUDE, 'coords'): cv.latitude,
    vol.Inclusive(CONF_LONGITUDE, 'coords'): cv.longitude,
    vol.Optional(CONF_COUNTRY_CODE, default=None): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the CO2signal sensor."""

    _LOGGER.debug("Setting up the CO2signal platform")

    token = config.get(CONF_TOKEN)
    lat = config.get(CONF_LATITUDE, hass.config.latitude)
    lon = config.get(CONF_LONGITUDE, hass.config.longitude)
    country_code = config.get(CONF_COUNTRY_CODE)

    if country_code is not None:
        location_type = 'country_code'
    else:
        location_type = 'coordinates'

    _LOGGER.debug("Setting up the sensor using the %s", location_type)

    devs = []

    devs.append(CO2Sensor(token,
                          country_code,
                          lat,
                          lon,
                          location_type))

    add_entities(devs, True)


class CO2Sensor(Entity):
    """Implementation of the CO2Signal sensor."""

    def __init__(self, token, country_code, lat, lon,
                 location_type):
        """Initialize the sensor."""

        self._token = token
        self._country_code = country_code
        self._latitude = lat
        self._longitude = lon
        self._location_type = location_type
        self._unit = 'CO2eq/kWh'

        if self._location_type == 'country_code':
            self._device_name = country_code
        else:
            self._device_name = '{lat}/{lon}'.format(lat = round(self._latitude, 2),
                                                     lon = round(self._longitude, 2))

        self._friendly_name = 'CO2 intensity - {}'.format(self._device_name)

        _LOGGER.debug("Initialise %s", self._friendly_name)

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
        return None

    @property
    def state(self):
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
            self._data = CO2Signal\
                .get_latest_carbon_intensity(self._token,
                                             country_code=self._country_code)
        elif self._location_type == 'coordinates':
            self._data = CO2Signal\
                .get_latest_carbon_intensity(self._token,
                                             latitude=self._latitude,
                                             longitude=self._longitude)
        else:
            raise ValueError("Unknown location type: {location_type}"
                             .format(location_type=self._location_type))

        self._data = round(self._data, 2)
