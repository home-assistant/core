"""Support for APRS device tracking."""
from __future__ import annotations

import logging
import threading
from typing import Any

import aprslib
from aprslib import ConnectionError as AprsConnectionError, LoginError
import geopy.distance
import voluptuous as vol

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    SeeCallback,
)
from homeassistant.const import (
    ATTR_GPS_ACCURACY,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_TIMEOUT,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify

DOMAIN = "aprs"

_LOGGER = logging.getLogger(__name__)

ATTR_ALTITUDE = "altitude"
ATTR_COURSE = "course"
ATTR_COMMENT = "comment"
ATTR_FROM = "from"
ATTR_FORMAT = "format"
ATTR_POS_AMBIGUITY = "posambiguity"
ATTR_SPEED = "speed"

CONF_CALLSIGNS = "callsigns"

DEFAULT_HOST = "rotate.aprs2.net"
DEFAULT_PASSWORD = "-1"
DEFAULT_TIMEOUT = 30.0

FILTER_PORT = 14580

MSG_FORMATS = ["compressed", "uncompressed", "mic-e"]

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_CALLSIGNS): cv.ensure_list,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.Coerce(float),
    }
)


def make_filter(callsigns: list) -> str:
    """Make a server-side filter from a list of callsigns."""
    return " ".join(f"b/{sign.upper()}" for sign in callsigns)


def gps_accuracy(gps: tuple[float, float], posambiguity: int) -> int:
    """Calculate the GPS accuracy based on APRS posambiguity."""

    pos_a_map = {0: 0, 1: 1 / 600, 2: 1 / 60, 3: 1 / 6, 4: 1}
    if posambiguity in pos_a_map:
        degrees = pos_a_map[posambiguity]

        gps2 = (gps[0], gps[1] + degrees)
        dist_m: float = geopy.distance.distance(gps, gps2).m

        accuracy = round(dist_m)
    else:
        message = f"APRS position ambiguity must be 0-4, not '{posambiguity}'."
        raise ValueError(message)

    return accuracy


def setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    see: SeeCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Set up the APRS tracker."""
    callsigns = config[CONF_CALLSIGNS]
    server_filter = make_filter(callsigns)

    callsign = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    host = config[CONF_HOST]
    timeout = config[CONF_TIMEOUT]
    aprs_listener = AprsListenerThread(callsign, password, host, server_filter, see)

    def aprs_disconnect(event: Event) -> None:
        """Stop the APRS connection."""
        aprs_listener.stop()

    aprs_listener.start()
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, aprs_disconnect)

    if not aprs_listener.start_event.wait(timeout):
        _LOGGER.error("Timeout waiting for APRS to connect")
        return False

    if not aprs_listener.start_success:
        _LOGGER.error(aprs_listener.start_message)
        return False

    _LOGGER.debug(aprs_listener.start_message)
    return True


class AprsListenerThread(threading.Thread):
    """APRS message listener."""

    def __init__(
        self,
        callsign: str,
        password: str,
        host: str,
        server_filter: str,
        see: SeeCallback,
    ) -> None:
        """Initialize the class."""
        super().__init__()

        self.callsign = callsign
        self.host = host
        self.start_event = threading.Event()
        self.see = see
        self.server_filter = server_filter
        self.start_message = ""
        self.start_success = False

        self.ais = aprslib.IS(
            self.callsign, passwd=password, host=self.host, port=FILTER_PORT
        )

    def start_complete(self, success: bool, message: str) -> None:
        """Complete startup process."""
        self.start_message = message
        self.start_success = success
        self.start_event.set()

    def run(self) -> None:
        """Connect to APRS and listen for data."""
        self.ais.set_filter(self.server_filter)

        try:
            _LOGGER.info(
                "Opening connection to %s with callsign %s", self.host, self.callsign
            )
            self.ais.connect()
            self.start_complete(
                True, f"Connected to {self.host} with callsign {self.callsign}."
            )
            self.ais.consumer(callback=self.rx_msg, immortal=True)
        except (AprsConnectionError, LoginError) as err:
            self.start_complete(False, str(err))
        except OSError:
            _LOGGER.info(
                "Closing connection to %s with callsign %s", self.host, self.callsign
            )

    def stop(self) -> None:
        """Close the connection to the APRS network."""
        self.ais.close()

    def rx_msg(self, msg: dict[str, Any]) -> None:
        """Receive message and process if position."""
        _LOGGER.debug("APRS message received: %s", str(msg))
        if msg[ATTR_FORMAT] in MSG_FORMATS:
            dev_id = slugify(msg[ATTR_FROM])
            lat = msg[ATTR_LATITUDE]
            lon = msg[ATTR_LONGITUDE]

            attrs = {}
            if ATTR_POS_AMBIGUITY in msg:
                pos_amb = msg[ATTR_POS_AMBIGUITY]
                try:
                    attrs[ATTR_GPS_ACCURACY] = gps_accuracy((lat, lon), pos_amb)
                except ValueError:
                    _LOGGER.warning(
                        "APRS message contained invalid posambiguity: %s", str(pos_amb)
                    )
            for attr in (ATTR_ALTITUDE, ATTR_COMMENT, ATTR_COURSE, ATTR_SPEED):
                if attr in msg:
                    attrs[attr] = msg[attr]

            self.see(dev_id=dev_id, gps=(lat, lon), attributes=attrs)
