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
from homeassistant.const import (
    CONF_NAME, CONF_TYPE, CONF_ZONE, CONF_MONITORED_VARIABLES)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['beautifulsoup4==4.6.0']

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'http://datasnapshot.pjm.com/content/InstantaneousLoad.aspx'

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)

PJM_RTO_TOTAL = "PJM RTO Total"
ICON_POWER = 'mdi:flash'

CONF_INSTANTANEOUS_ZONE_LOAD = 'instantaneous_zone_load'
CONF_INSTANTANEOUS_TOTAL_LOAD = 'instantaneous_total_load'

SENSOR_TYPES = {
    CONF_INSTANTANEOUS_ZONE_LOAD: ["PJM Instantaneous Zone Load", 'MW'],
    CONF_INSTANTANEOUS_TOTAL_LOAD: ["PJM Instantaneous Total Load", 'MW'],
}

SENSORS_SCHEMA = vol.Schema({
    vol.Required(CONF_TYPE): vol.In(SENSOR_TYPES),
    vol.Optional(CONF_ZONE): cv.string,
    vol.Optional(CONF_NAME): cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_VARIABLES): [SENSORS_SCHEMA],
})


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Set up the PJM sensor."""
    pjm_data = PJMData(hass.loop, async_get_clientsession(hass))
    dev = []

    for variable in config[CONF_MONITORED_VARIABLES]:
        dev.append(PJMSensor(
            pjm_data, variable[CONF_TYPE],
            variable.get(CONF_ZONE), variable.get(CONF_NAME)))

    async_add_devices(dev, True)


class PJMSensor(Entity):
    """Implementation of a PJM sensor."""

    def __init__(self, pjm_data, sensor_type, zone, name):
        """Initialize the sensor."""
        self._pjm_data = pjm_data
        if name:
            self._name = name
        else:
            self._name = SENSOR_TYPES[sensor_type][0]
            if sensor_type == CONF_INSTANTANEOUS_ZONE_LOAD:
                self._name += ' ' + zone
        self._type = sensor_type
        self._state = None
        self._zone = zone
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON_POWER

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    async def async_update(self):
        """Parse the PJM data and set our state."""
        from bs4 import BeautifulSoup

        try:
            await self._pjm_data.async_update()

            if not self._pjm_data.data:
                # No data; return
                return

            soup = BeautifulSoup(self._pjm_data.data, "html.parser")
            search_text = PJM_RTO_TOTAL
            if self._type == CONF_INSTANTANEOUS_ZONE_LOAD:
                search_text = self._zone + ' Zone'
            # Find the table row that has the zone we want
            found_text = soup.find('td', text=search_text)
            # The next cell contains the power data
            text_data = found_text.find_next_sibling('td').text
            # Convert number string with commas to int
            self._state = int(text_data.replace(',', ''))

        except (ValueError, KeyError):
            _LOGGER.warning("Could not update status for %s", self._name)
        except AttributeError as err:
            _LOGGER.error("Could not update status for PJM: %s", err)


class PJMData(object):
    """Get data from PJM."""

    def __init__(self, loop, websession):
        """Initialize the data object."""
        self._loop = loop
        self._websession = websession
        self.data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest data from PJM."""
        try:
            with async_timeout.timeout(60, loop=self._loop):
                response = await self._websession.get(_RESOURCE)
                self.data = await response.text()

        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error("Could not get data from PJM: %s", err)
