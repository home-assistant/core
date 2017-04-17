"""
homeassistant.components.sensor.solar_elevation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Shows the current CPU speed.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.solar_elevation/
"""
import logging
import urllib


from homeassistant.helpers.entity import Entity
import homeassistant.util as util
import homeassistant.util.dt as dt_util


REQUIREMENTS = ['astral==0.8.1']

ENTITY_ID = "sensor.solar_elevation"

CONF_SUN_ELEVATION = 'elevation'

SUN_DOMAIN = "sun"
DOMAIN = "solar_elevation"


_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-variable
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the sensor. """

    try:
        from astral import Location, GoogleGeocoder
    except ImportError:
        _LOGGER.exception(
            "Unable to import astral. "
            "Did you maybe not install the 'astral.py' package?")
        return False

    # Logic stolen from Sun component
    if None in (hass.config.latitude, hass.config.longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return False

    latitude = util.convert(hass.config.latitude, float)
    longitude = util.convert(hass.config.longitude, float)
    errors = []

    if latitude is None:
        errors.append('Latitude needs to be a decimal value')
    elif -90 > latitude < 90:
        errors.append('Latitude needs to be -90 .. 90')

    if longitude is None:
        errors.append('Longitude needs to be a decimal value')
    elif -180 > longitude < 180:
        errors.append('Longitude needs to be -180 .. 180')

    if errors:
        _LOGGER.error('Invalid configuration received: %s', ", ".join(errors))
        return False

    platform_config = config.get(SUN_DOMAIN, {})

    elevation = platform_config.get(CONF_SUN_ELEVATION)

    location = Location(('', '', latitude, longitude, hass.config.time_zone,
                         elevation or 0))

    if elevation is None:
        google = GoogleGeocoder()
        try:
            google._get_elevation(location)  # pylint: disable=protected-access
            _LOGGER.info(
                'Retrieved elevation from Google: %s', location.elevation)
        except urllib.error.URLError:
            # If no internet connection available etc.
            pass

    add_devices([SolarElevation(hass, location)])


class SolarElevation(Entity):
    """ Represents the Sun's elevation. """

    entity_id = ENTITY_ID

    def __init__(self, hass, location):
        self.hass = hass
        self.location = location
        self._state = None
        self._unit_of_measurement = 'Degrees'
        self.update()

    @property
    def name(self):
        return "Solar Elevation"

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self):
        """ Unit the value is expressed in. """
        return self._unit_of_measurement

    @property
    def solar_elevation(self):
        """ Returns the angle the sun is above the horizon"""
        from astral import Astral
        return Astral().solar_elevation(
            dt_util.utcnow(), self.location.latitude, self.location.longitude)

    def update(self):
        """ Update solar elevation. """
        self._state = round(self.solar_elevation, 2)
        self.update_ha_state()
