"""
Sensor for PostNL packages.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.postnl/
"""
from collections import defaultdict
import logging
from datetime import timedelta, datetime
import re
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME, CONF_USERNAME, CONF_PASSWORD,
                                 ATTR_ATTRIBUTION)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['postnl_api==0.3']

_LOGGER = logging.getLogger(__name__)
CONF_UPDATE_INTERVAL = 'update_interval'
DOMAIN = 'postnl'
ICON = 'mdi:package-variant-closed'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_UPDATE_INTERVAL, default=timedelta(seconds=1800)):
        vol.All(cv.time_period, cv.positive_timedelta),
})

# pylint: disable=unused-argument


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the PostNL platform."""

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    name = config.get(CONF_NAME)
    update_interval = config.get(CONF_UPDATE_INTERVAL)

    from postnl_api import PostNL_API

    try:
        api = PostNL_API(username, password)

    except Exception:
        _LOGGER.exception('Wrong Credentials')
        return False

    add_devices([PostNLSensor(username, password, name, update_interval)], True)


class PostNLSensor(Entity):
    """PostNL Sensor."""

    def __init__(self, username, password, name, interval):
        """Initialize the sensor."""
        self.friendly_name = name
        # self._name = DOMAIN + '_' + name
        self._name = name
        self._attributes = None
        self._state = None

        self._username = username
        self._password = password

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

        if self._state == 1:
            return 'package'
        else:
            return 'packages'

    def _update(self):
        """Update device state."""
        from postnl_api import PostNL_API

        api = PostNL_API(self._username, self._password)
        shipments = api.get_relevant_shipments()
        status_counts = defaultdict(str)

        def parse_date(date):
            return datetime.strptime(date.group(1).replace(' ', '')[:-6], '%Y-%m-%dT%H:%M:%S').strftime('%d-%m-%Y')

        def parse_time(date):
            return datetime.strptime(date.group(1).replace(' ', '')[:-6], '%Y-%m-%dT%H:%M:%S').strftime('%H:%M')

        for shipment in shipments:
            status = shipment['status']['formatted']['short']
            status = re.sub(r'{(?:Date|dateAbs):(.*?)}', parse_date, status)
            status = re.sub(r'{(?:time):(.*?)}', parse_time, status)

            name = shipment['settings']['title']
            status_counts[name] = status

        self._attributes = {
            ATTR_ATTRIBUTION: 'Information provided by PostNL'
        }
        self._attributes.update(status_counts)
        self._state = len(status_counts)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return ICON
