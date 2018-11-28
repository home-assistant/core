"""
"""

import logging

from datetime import timedelta
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, ATTR_ATTRIBUTION
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'VRT NWS'
DEFAULT_ICON = 'mdi:newspaper'

CONF_UPDATE_INTERVAL = 'update_interval'

REQUIREMENTS = ['xmltodict==0.11.0', 'requests_xml==0.2.3']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_UPDATE_INTERVAL, default=timedelta(seconds=180)): (
        vol.All(cv.time_period, cv.positive_timedelta)),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """"""
    from requests_xml import XMLSession
    session = XMLSession()

    name = config.get(CONF_NAME)
    interval = config.get(CONF_UPDATE_INTERVAL)

    add_entities([VRTNWSFeedSensor(name, session)], True)


class VRTNWSFeedSensor(Entity):
    """"""

    def __init__(self, name, session):
        """"""
        self._name = name
        self._session = session
        self._state = None
        self.update = Throttle(interval)(self._update)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return ""

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return DEFAULT_ICON

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_ATTRIBUTION: "",
        }

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    def update(self):
        """Set the state to the available amount of bikes as a number"""
        import xmltodict

        response = self._session.get('https://www.vrt.be/vrtnws/nl.rss.articles.xml')

        entries = xmltodict.parse(response.xml.xml).get('feed').get('entry')
        first_entry = entries[0]
        _LOGGER.error(first_entry["summary"].get("#text"))
        self._state = first_entry["summary"].get("#text")
