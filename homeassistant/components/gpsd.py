"""
Support for GPSD.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/gpsd/
"""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.util as util
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_point_in_utc_time
from homeassistant.util import dt as dt_util
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (ATTR_LATITUDE, ATTR_LONGITUDE, STATE_UNKNOWN)

REQUIREMENTS = ['gps3==0.33.2']

DOMAIN = "gpsd"
ENTITY_ID = "{}.gps".format(DOMAIN)

CONF_HOST = 'host'
CONF_PORT = 'port'
DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 2947

ATTR_GPS_TIME = 'gps_time'
ATTR_ELEVATION = 'elevation'
ATTR_SPEED = 'speed'
ATTR_CLIMB = 'climb'
ATTR_MODE = 'mode'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """Setup the GPSD component."""
    #from gps3 import gps3

    conf = config[DOMAIN]
    host = util.convert(conf.get(CONF_HOST), str, DEFAULT_HOST)
    port = util.convert(conf.get(CONF_PORT), str, DEFAULT_PORT)

    # Will hopefully be possible with the next gps3 update
    # https://github.com/wadda/gps3/issues/11
    # try:
    #     gpsd_socket = gps3.GPSDSocket()
    #     gpsd_socket.connect(host=host, port=port)
    # except OSError:
    #     _LOGGER.warning('Not able to connect to GPSD')
    #     return False

    gpsd = Gpsd(hass, host, port)
    gpsd.point_in_time_listener(dt_util.utcnow())

    return True


class Gpsd(Entity):
    """Representation of a GPS receiver available via GPSD."""

    entity_id = ENTITY_ID

    def __init__(self, hass, host, port):
        """Initialize the GPSD."""
        from gps3.agps3threaded import AGPS3mechanism

        self.hass = hass
        self._host = host
        self._port = port

        self.agps_thread = AGPS3mechanism()
        self.agps_thread.stream_data(host=self._host, port=self._port)
        self.agps_thread.run_thread()

    @property
    def name(self):
        """Return the name."""
        return "GPS"

    # pylint: disable=no-member
    @property
    def state(self):
        """Return the state of GPSD."""
        if self.agps_thread.data_stream.mode == 3:
            return "3D Fix"
        elif self.agps_thread.data_stream.mode == 2:
            return "2D Fix"
        else:
            return STATE_UNKNOWN

    @property
    def state_attributes(self):
        """Return the state attributes of GPS."""
        return {
            ATTR_LATITUDE: self.agps_thread.data_stream.lat,
            ATTR_LONGITUDE: self.agps_thread.data_stream.lon,
            ATTR_ELEVATION: self.agps_thread.data_stream.alt,
            ATTR_GPS_TIME: self.agps_thread.data_stream.time,
            ATTR_SPEED: self.agps_thread.data_stream.speed,
            ATTR_CLIMB: self.agps_thread.data_stream.climb,
            ATTR_MODE: self.agps_thread.data_stream.mode,
        }

    def point_in_time_listener(self, now):
        """Called when the state needs an update."""
        self.update_ha_state()

        # Schedule next update at next_change+10 second
        track_point_in_utc_time(
            self.hass, self.point_in_time_listener,
            now + timedelta(seconds=10))
