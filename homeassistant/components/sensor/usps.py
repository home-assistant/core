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
from homeassistant.util.dt import now, parse_datetime
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['myusps==1.1.2']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'usps'
SCAN_INTERVAL = timedelta(minutes=30)
COOKIE = 'usps_cookies.pickle'
STATUS_DELIVERED = 'delivered'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_NAME): cv.string
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the USPS platform."""
    import myusps
    try:
        cookie = hass.config.path(COOKIE)
        session = myusps.get_session(
            config.get(CONF_USERNAME), config.get(CONF_PASSWORD),
            cookie_path=cookie)
    except myusps.USPSError:
        _LOGGER.exception('Could not connect to My USPS')
        return False

    add_devices([USPSPackageSensor(session, config.get(CONF_NAME)),
                 USPSMailSensor(session, config.get(CONF_NAME))], True)


class USPSPackageSensor(Entity):
    """USPS Package Sensor."""

    def __init__(self, session, name):
        """Initialize the sensor."""
        self._session = session
        self._name = name
        self._attributes = None
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} packages'.format(self._name or DOMAIN)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
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
        return 'mdi:package-variant-closed'


class USPSMailSensor(Entity):
    """USPS Mail Sensor."""

    def __init__(self, session, name):
        """Initialize the sensor."""
        self._session = session
        self._name = name
        self._attributes = None
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} mail'.format(self._name or DOMAIN)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Update device state."""
        import myusps
        self._state = len(myusps.get_mail(self._session))

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        import myusps
        return {
            ATTR_ATTRIBUTION: myusps.ATTRIBUTION
        }

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return 'mdi:mailbox'
