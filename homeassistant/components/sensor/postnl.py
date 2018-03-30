"""
Sensor for PostNL packages.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.postnl/
"""
import logging
from datetime import timedelta, datetime
import re
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME, CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL,
                                 ATTR_ATTRIBUTION)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['postnl_api==0.3']

_LOGGER = logging.getLogger(__name__)
DEFAULT_NAME = 'postnl'
ICON = 'mdi:package-variant-closed'
ATTRIBUTION = 'Information provided by PostNL'
SCAN_INTERVAL = timedelta(minutes=30)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL):
    cv.time_period,
})

# pylint: disable=unused-argument


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the PostNL platform."""

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    name = config.get(CONF_NAME)
    update_interval = config.get(CONF_SCAN_INTERVAL)

    from postnl_api import PostNL_API

    try:
        api = PostNL_API(username, password)

    except Exception:
        _LOGGER.exception("Can't connect to the PostNL webservice")
        return

    add_devices([PostNLSensor(api, name, update_interval)], True)


class PostNLSensor(Entity):
    """PostNL Sensor."""

    def __init__(self, api, name, interval):
        """Initialize the sensor."""
        self.friendly_name = name
        self._name = name
        self._attributes = None
        self._state = None

        self._api = api

        self.update = Throttle(interval)(self._update)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return 'package(s)'

    def _update(self):
        """Update device state."""

        shipments = self._api.get_relevant_shipments()
        status_counts = {}

        def parse_date(date):
            return datetime.strptime(date.group(1)
                                     .replace(' ', '')[:-6], '%Y-%m-%dT%H:%M:%S').strftime('%d-%m-%Y')

        def parse_time(date):
            return datetime.strptime(date.group(1)
                                     .replace(' ', '')[:-6], '%Y-%m-%dT%H:%M:%S').strftime('%H:%M')

        for shipment in shipments:
            status = shipment['status']['formatted']['short']
            status = re.sub(r'{(?:Date|dateAbs):(.*?)}', parse_date, status)
            status = re.sub(r'{(?:time):(.*?)}', parse_time, status)

            name = shipment['settings']['title']
            status_counts[name] = status

        self._attributes = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            **status_counts
        }

        self._state = len(status_counts)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return ICON
