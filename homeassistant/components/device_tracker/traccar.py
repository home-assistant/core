"""
Support for Traccar location sharing.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.traccar/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA, SOURCE_TYPE_GPS)
from homeassistant.const import ATTR_ID, CONF_PASSWORD, \
    CONF_USERNAME, CONF_URL
import homeassistant.util.dt as dt
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import track_time_interval
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

ATTR_ADDRESS = 'address'
ATTR_FULL_NAME = 'full_name'
ATTR_LAST_SEEN = 'last_seen'
ATTR_SPEED = 'speed'
ATTR_ACCURACY = 'accuracy'
ATTR_BATTERY = 'battery_level'

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=30)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_URL): cv.url,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})


def setup_scanner(hass, config: ConfigType, see, discovery_info=None):
    """Set up the scanner."""
    scanner = TraccarScanner(hass, config, see)
    return scanner if scanner.success_init else None


class TraccarScanner(object):
    """This class queries a Traccar website to get devices position."""

    def __init__(self, hass, config: ConfigType, see) -> None:
        """Initialize the scanner."""

        self.see = see
        self.baseurl = config.get(CONF_URL)
        self.username = config.get(CONF_USERNAME)
        self.password = config.get(CONF_PASSWORD)
        self.positions = None
        self.devices = None

        track_time_interval(
            hass,
            self.update_traccar_data,
            MIN_TIME_BETWEEN_SCANS
        )

        data = self.update_traccar_data()
        self.success_init = data is not None
        _LOGGER.info("Scanner initialized")

    def update_traccar_data(self, now=None):
        """Update Traccar devices position."""

        self.positions = self.get_traccar_data("/api/positions")
        self.devices = self.get_traccar_data("/api/devices")
        return self.parse_traccar_data()

    def get_traccar_data(self, url):
        """Retrieve data from Traccar and return result."""
        import requests

        try:
            response = requests.get(
                self.baseurl + url,
                auth=(self.username, self.password),
                timeout=4
            )
        except requests.exceptions.Timeout:
            _LOGGER.exception("Connection to the server timed out")
            return
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            _LOGGER.exception(
                "Failed to authenticate, check your username and password")
            return
        else:
            _LOGGER.error("Invalid response from Traccar: %s", response)

    def parse_traccar_data(self):
        """Parse data from Traccar result."""

        devices = self.devices
        positions = self.positions

        try:
            for dev in devices:
                for pos in positions:
                    if pos['deviceId'] == dev['id']:
                        attrs = {
                            ATTR_ID: dev['id'],
                            ATTR_FULL_NAME: dev['name'],
                            ATTR_ADDRESS: pos['address'],
                            ATTR_SPEED: float(pos['speed']),
                            ATTR_LAST_SEEN: dt.as_local(
                                dt.parse_datetime(pos['fixTime'])),
                            ATTR_BATTERY: int(
                                pos['attributes']['batteryLevel'])
                        }
                        self.see(
                            dev_id=dev['name'],
                            gps=(pos['latitude'], pos['longitude']),
                            source_type=SOURCE_TYPE_GPS,
                            gps_accuracy=float(pos['accuracy']),
                            attributes=attrs,
                        )
            return True
        except TypeError:
            _LOGGER.warning(
                "An error occourred parsing reply from Traccar server")
            return None
