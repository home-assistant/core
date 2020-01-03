"""
Support for the Environment Canada water service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/integrations/canada_hydrometric/
"""
from datetime import timedelta
import logging
import re

from env_canada import ECHydro
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_LOCATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=10)

ATTR_UPDATED = "updated"
ATTR_STATION = "station"

CONF_ATTRIBUTION = "Data provided by Environment Canada"
CONF_STATION = "station"


def validate_station(station):
    """Check that the station ID is well-formed."""
    if station is None:
        return
    if not re.fullmatch(r"[A-Z]{2}/\d{2}[A-Z]{2}\d{3}", station):
        raise vol.error.Invalid('Station ID must be of the form "XX/##XX###"')
    return station


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_STATION): validate_station,
        vol.Inclusive(CONF_LATITUDE, "latlon"): cv.latitude,
        vol.Inclusive(CONF_LONGITUDE, "latlon"): cv.longitude,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Environment Canada hydrometric sensor."""

    if config.get(CONF_STATION):
        province, station = config[CONF_STATION].split("/")
        ec_hydro = ECHydro(province=province, station=station)
    else:
        lat = config.get(CONF_LATITUDE, hass.config.latitude)
        lon = config.get(CONF_LONGITUDE, hass.config.longitude)
        ec_hydro = ECHydro(coordinates=(lat, lon))

    sensor_list = ["water_level", "discharge"]
    add_entities([ECSensor(sensor_type, ec_hydro) for sensor_type in sensor_list], True)


class ECSensor(Entity):
    """Implementation of an Environment Canada hydrometric sensor."""

    def __init__(self, sensor_type, ec_hydro):
        """Initialize the sensor."""
        self.sensor_type = sensor_type
        self.ec_hydro = ec_hydro

        self._unique_id = None
        self._name = None
        self._state = None
        self._attr = None
        self._unit = None

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._attr

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return self._unit

    def update(self):
        """Update current measurements."""
        self.ec_hydro.update()

        measurements = self.ec_hydro.measurements
        sensor_data = measurements.get(self.sensor_type)

        self._unique_id = "{}-{}".format(self.ec_hydro.station, self.sensor_type)
        self._attr = {}

        self._name = sensor_data.get("label")
        self._state = sensor_data.get("value")
        self._unit = sensor_data.get("unit")

        timestamp = self.ec_hydro.timestamp
        if timestamp:
            updated_utc = timestamp.isoformat()
        else:
            updated_utc = None

        self._attr.update(
            {
                ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
                ATTR_UPDATED: updated_utc,
                ATTR_LOCATION: self.ec_hydro.location,
                ATTR_STATION: self.ec_hydro.station,
            }
        )
