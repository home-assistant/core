"""Support for the CO2signal platform."""
from datetime import timedelta
import logging

import CO2Signal
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_TOKEN,
    ENERGY_KILO_WATT_HOUR,
)
import homeassistant.helpers.config_validation as cv

CONF_COUNTRY_CODE = "country_code"

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=3)

ATTRIBUTION = "Data provided by CO2signal"

MSG_LOCATION = (
    "Please use either coordinates or the country code. "
    "For the coordinates, "
    "you need to use both latitude and longitude."
)
CO2_INTENSITY_UNIT = f"CO2eq/{ENERGY_KILO_WATT_HOUR}"
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_TOKEN): cv.string,
        vol.Inclusive(CONF_LATITUDE, "coords", msg=MSG_LOCATION): cv.latitude,
        vol.Inclusive(CONF_LONGITUDE, "coords", msg=MSG_LOCATION): cv.longitude,
        vol.Optional(CONF_COUNTRY_CODE): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the CO2signal sensor."""
    token = config[CONF_TOKEN]
    lat = config.get(CONF_LATITUDE, hass.config.latitude)
    lon = config.get(CONF_LONGITUDE, hass.config.longitude)
    country_code = config.get(CONF_COUNTRY_CODE)

    _LOGGER.debug("Setting up the sensor using the %s", country_code)

    add_entities([CO2Sensor(token, country_code, lat, lon)], True)


class CO2Sensor(SensorEntity):
    """Implementation of the CO2Signal sensor."""

    _attr_icon = "mdi:molecule-co2"
    _attr_unit_of_measurement = CO2_INTENSITY_UNIT

    def __init__(self, token, country_code, lat, lon):
        """Initialize the sensor."""
        self._token = token
        self._country_code = country_code
        self._latitude = lat
        self._longitude = lon

        if country_code is not None:
            device_name = country_code
        else:
            device_name = f"{round(self._latitude, 2)}/{round(self._longitude, 2)}"

        self._attr_name = f"CO2 intensity - {device_name}"
        self._attr_extra_state_attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}

    def update(self):
        """Get the latest data and updates the states."""

        _LOGGER.debug("Update data for %s", self.name)

        if self._country_code is not None:
            data = CO2Signal.get_latest_carbon_intensity(
                self._token, country_code=self._country_code
            )
        else:
            data = CO2Signal.get_latest_carbon_intensity(
                self._token, latitude=self._latitude, longitude=self._longitude
            )

        self._attr_state = round(data, 2)
