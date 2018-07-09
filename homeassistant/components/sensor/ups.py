"""
Sensor for UPS packages.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.ups/
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
from homeassistant.util.dt import now, parse_date
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['upsmychoice==1.0.6']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'ups'
COOKIE = 'upsmychoice_cookies.pickle'
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


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the UPS platform."""
    import upsmychoice
    try:
        cookie = hass.config.path(COOKIE)
        session = upsmychoice.get_session(
            config.get(CONF_USERNAME), config.get(CONF_PASSWORD),
            cookie_path=cookie)
    except upsmychoice.UPSError:
        _LOGGER.exception("Could not connect to UPS My Choice")
        return False

    add_devices([UPSSensor(session, config.get(CONF_NAME),
                           config.get(CONF_UPDATE_INTERVAL))], True)


class UPSSensor(Entity):
    """UPS Sensor."""

    def __init__(self, session, name, interval):
        """Initialize the sensor."""
        self._session = session
        self._name = name
        self._attributes = None
        self._state = None
        self.update = Throttle(interval)(self._update)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name or DOMAIN

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return 'packages'

    def _update(self):
        """Update device state."""
        import upsmychoice
        status_counts = defaultdict(int)
        try:
            for package in upsmychoice.get_packages(self._session):
                status = slugify(package['status'])
                skip = status == STATUS_DELIVERED and \
                    parse_date(package['delivery_date']) < now().date()
                if skip:
                    continue
                status_counts[status] += 1
        except upsmychoice.UPSError:
            _LOGGER.error('Could not connect to UPS My Choice account')

        self._attributes = {
            ATTR_ATTRIBUTION: upsmychoice.ATTRIBUTION
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
