"""
Support for PJM data.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.pjm/
"""
import asyncio
from datetime import timedelta
import logging

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['beautifulsoup4==4.6.0']

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'http://datasnapshot.pjm.com/content/InstantaneousLoad.aspx'

PJM_RTO_TOTAL = "PJM RTO Total"

SCAN_INTERVAL = timedelta(minutes=5)

ICON_POWER = 'mdi:flash'

CONF_MONITORED_FEEDS = 'monitored_feeds'
CONF_SENSOR_TYPE = 'type'
CONF_INSTANTANEOUS_ZONE_LOAD = 'instantaneous_zone_load'
CONF_INSTANTANEOUS_TOTAL_LOAD = 'instantaneous_total_load'
CONF_ZONE = 'zone'

SENSOR_TYPES = {
    CONF_INSTANTANEOUS_ZONE_LOAD: ["PJM Instantaneous Zone Load", 'MW'],
    CONF_INSTANTANEOUS_TOTAL_LOAD: ["PJM Instantaneous Total Load", 'MW'],
}

TYPES_SCHEMA = vol.In(SENSOR_TYPES)

SENSORS_SCHEMA = vol.Schema({
    vol.Required(CONF_SENSOR_TYPE): TYPES_SCHEMA,
    vol.Optional(CONF_ZONE): cv.string,
    vol.Optional(CONF_NAME): cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_FEEDS): [SENSORS_SCHEMA],
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the PJM sensor."""
    websession = async_get_clientsession(hass)
    dev = []

    for variable in config[CONF_MONITORED_FEEDS]:
        dev.append(PJMSensor(
            hass.loop, websession, variable[CONF_SENSOR_TYPE],
            variable.get(CONF_ZONE), variable.get(CONF_NAME)))

    async_add_devices(dev, True)


class PJMSensor(Entity):
    """Implementation of a PJM sensor."""

    def __init__(self, loop, websession, sensor_type, zone, name):
        """Initialize the sensor."""
        self.loop = loop
        self.websession = websession
        if name:
            self._name = name
        else:
            self._name = SENSOR_TYPES[sensor_type][0]
            if sensor_type == CONF_INSTANTANEOUS_ZONE_LOAD:
                self._name += ' ' + zone
        self.type = sensor_type
        self._state = None
        if zone:
            self.zone = zone
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if self.type == CONF_INSTANTANEOUS_ZONE_LOAD:
            return ICON_POWER
        if self.type == CONF_INSTANTANEOUS_TOTAL_LOAD:
            return ICON_POWER

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @asyncio.coroutine
    def async_update(self):
        """Get the PJM data from the web service."""
        from bs4 import BeautifulSoup

        try:
            with async_timeout.timeout(60, loop=self.loop):
                response = yield from self.websession.get(_RESOURCE)
                text = yield from response.text()
                soup = BeautifulSoup(text, "html.parser")
                search_text = PJM_RTO_TOTAL
                if self.type == CONF_INSTANTANEOUS_ZONE_LOAD:
                    search_text = self.zone + ' Zone'
                # Find the table row that has the zone we want
                found_text = soup.find('td', text=search_text)
                # The next cell contains the power data
                self._state = found_text.find_next_sibling('td').text

        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error("Could not get data from PJM: %s", err)
        except (ValueError, KeyError):
            _LOGGER.warning("Could not update status for %s", self.name)
        except AttributeError as err:
            _LOGGER.error("Could not get data from PJM: %s", err)
