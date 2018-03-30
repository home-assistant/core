"""
Support for Google Maps location sharing.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.google_maps/
"""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA, SOURCE_TYPE_GPS)
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.event import track_time_interval
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['locationsharinglib==0.4.0']

CREDENTIALS_FILE = '.google_maps_location_sharing.cookies'

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=30)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})


def setup_scanner(hass, config: ConfigType, see, discovery_info=None):
    """Set up the scanner."""
    scanner = GoogleMapsScanner(hass, config, see)
    return scanner.success_init


class GoogleMapsScanner(object):
    """Representation of an Google Maps location sharing account."""

    def __init__(self, hass, config: ConfigType, see) -> None:
        """Initialize the scanner."""
        from locationsharinglib import Service
        from locationsharinglib.locationsharinglibexceptions import InvalidUser

        self.see = see
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]

        try:
            self.service = Service(self.username, self.password,
                                   hass.config.path(CREDENTIALS_FILE))
            self._update_info()

            track_time_interval(
                hass, self._update_info, MIN_TIME_BETWEEN_SCANS)

            self.success_init = True

        except InvalidUser:
            _LOGGER.error('You have specified invalid login credentials')
            self.success_init = False

    def _update_info(self, now=None):
        for person in self.service.get_all_people():
            dev_id = 'google_maps_{0}'.format(slugify(person.id))

            attrs = {
                'id': person.id,
                'nickname': person.nickname,
                'full_name': person.full_name,
                'last_seen': person.datetime,
                'address': person.address
            }
            self.see(
                dev_id=dev_id,
                gps=(person.latitude, person.longitude),
                picture=person.picture_url,
                source_type=SOURCE_TYPE_GPS,
                attributes=attrs
            )
