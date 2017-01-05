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
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, ATTR_ATTRIBUTION
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['myusps==1.0.0']

_LOGGER = logging.getLogger(__name__)

CONF_UPDATE_INTERVAL = 'update_interval'
ICON = 'mdi:package-variant-closed'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_UPDATE_INTERVAL, default=timedelta(seconds=1800)): (
        vol.All(cv.time_period, cv.positive_timedelta)),
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the USPS platform."""
    import myusps
    try:
        session = myusps.get_session(config.get(CONF_USERNAME),
                                     config.get(CONF_PASSWORD))
    except myusps.USPSError:
        _LOGGER.exception('Could not connect to My USPS')
        return False

    add_devices([USPSSensor(session, config.get(CONF_UPDATE_INTERVAL))])


class USPSSensor(Entity):
    """USPS Sensor."""

    def __init__(self, session, interval):
        """Initialize the sensor."""
        import myusps
        self._session = session
        self._profile = myusps.get_profile(session)
        self._packages = None
        self.update = Throttle(interval)(self._update)
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._profile.get('address')

    @property
    def state(self):
        """Return the state of the sensor."""
        return len(self._packages)

    def _update(self):
        """Update device state."""
        import myusps
        self._packages = myusps.get_packages(self._session)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        import myusps
        status_counts = defaultdict(int)
        for package in self._packages:
            status_counts[slugify(package['status'])] += 1
        attributes = {
            ATTR_ATTRIBUTION: myusps.ATTRIBUTION
        }
        attributes.update(status_counts)
        return attributes

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return ICON
