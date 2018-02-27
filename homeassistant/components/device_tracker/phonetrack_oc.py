"""
Support for PhoneTrackOC device tracking.
"""
import logging
import urllib.parse
from datetime import timedelta

import requests

from homeassistant.const import CONF_DEVICES, CONF_TOKEN, CONF_URL
from homeassistant.helpers.event import track_time_interval
from homeassistant.util import slugify, Throttle

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=5)


def setup_scanner(hass, config: dict, see, discovery_info=None):
    """Setup the PhoneTrack-OC scanner."""
    PhoneTrackOCDeviceTracker(hass, config, see)
    return True


class PhoneTrackOCDeviceTracker(object):
    """
    A device tracker fetching last position from the PhoneTrackOC Nextcloud
    app.
    """
    def __init__(self, hass, config: dict, see):
        """Initialize the PhoneTrackOC tracking."""
        self.hass = hass
        self.url = config.get(CONF_URL)
        self.token = config.get(CONF_TOKEN)
        self.devices = config.get(CONF_DEVICES)
        self.see = see
        self._update_info()

        track_time_interval(
            self.hass, self._update_info, UPDATE_INTERVAL
        )

    @Throttle(UPDATE_INTERVAL)
    def _update_info(self, now=None):
        """Update the device info."""
        _LOGGER.debug("Updating devices %s", now)
        data = requests.get(urllib.parse.urljoin(self.url, self.token)).json()
        data = data[self.token]
        for device in self.devices:
            if device not in data.keys():
                _LOGGER.info('Device %s is not available.', device)
                continue
            lat, lon = data[device]['lat'], data[device]['lon']
            accuracy = data[device]['accuracy']
            battery = data[device]['batterylevel']
            self.see(
                dev_id=slugify(device),
                gps=(lat, lon), gps_accuracy=accuracy,
                battery=battery
            )
        return True
