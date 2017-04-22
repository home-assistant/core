"""
Sensor for USPS packages.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.usps/
"""
from collections import defaultdict
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME, CONF_USERNAME, CONF_PASSWORD,
                                 ATTR_ATTRIBUTION)
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify
from homeassistant.util import Throttle
from homeassistant.util.dt import now, parse_datetime
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['myusps==1.0.5']

_LOGGER = logging.getLogger(__name__)

COOKIE = 'usps_cookies.pickle'
CONF_UPDATE_INTERVAL = 'update_interval'
ICON = 'mdi:package-variant-closed'
STATUS_DELIVERED = 'delivered'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_UPDATE_INTERVAL, default=timedelta(seconds=1800)): (
        vol.All(cv.time_period, cv.positive_timedelta)),
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the USPS platform."""
    import myusps
    try:
        cookie = hass.config.path(COOKIE)
        session = myusps.get_session(config.get(CONF_USERNAME),
                                     config.get(CONF_PASSWORD),
                                     cookie_path=cookie)
    except myusps.USPSError:
        _LOGGER.exception('Could not connect to My USPS')
        return False

    add_devices([USPSSensor(session, config.get(CONF_NAME),
                            config.get(CONF_UPDATE_INTERVAL))])


class USPSSensor(Entity):
    """USPS Sensor."""

    def __init__(self, session, name, interval):
        """Initialize the sensor."""
        import myusps
        self._session = session
        self._name = name
        self._profile = myusps.get_profile(session)
        self._attributes = None
        self._state = None
        self.update = Throttle(interval)(self._update)
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name or self._profile.get('address')

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def _update(self):
        """Update device state."""
        import myusps
        status_counts = defaultdict(int)
        for package in myusps.get_packages(self._session):
            status = slugify(package['primary_status'])
            if status == STATUS_DELIVERED and \
                    parse_datetime(package['date']).date() < now().date():
                continue
            status_counts[status] += 1
        self._attributes = {
            ATTR_ATTRIBUTION: myusps.ATTRIBUTION
        }
        self._attributes.update(status_counts)
        self._state = sum(status_counts.values())

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return ICON
