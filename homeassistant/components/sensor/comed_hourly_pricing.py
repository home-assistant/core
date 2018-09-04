"""
Support for ComEd Hourly Pricing data.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.comed_hourly_pricing/
"""
import asyncio
from datetime import timedelta
import json
import logging

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_NAME, CONF_OFFSET, STATE_UNKNOWN)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'https://hourlypricing.comed.com/api'

SCAN_INTERVAL = timedelta(minutes=5)

CONF_ATTRIBUTION = "Data provided by ComEd Hourly Pricing service"
CONF_CURRENT_HOUR_AVERAGE = 'current_hour_average'
CONF_FIVE_MINUTE = 'five_minute'
CONF_MONITORED_FEEDS = 'monitored_feeds'
CONF_SENSOR_TYPE = 'type'

SENSOR_TYPES = {
    CONF_FIVE_MINUTE: ['ComEd 5 Minute Price', 'c'],
    CONF_CURRENT_HOUR_AVERAGE: ['ComEd Current Hour Average Price', 'c'],
}

TYPES_SCHEMA = vol.In(SENSOR_TYPES)

SENSORS_SCHEMA = vol.Schema({
    vol.Required(CONF_SENSOR_TYPE): TYPES_SCHEMA,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_OFFSET, default=0.0): vol.Coerce(float),
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_FEEDS): [SENSORS_SCHEMA],
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_entities,
                         discovery_info=None):
    """Set up the ComEd Hourly Pricing sensor."""
    websession = async_get_clientsession(hass)
    dev = []

    for variable in config[CONF_MONITORED_FEEDS]:
        dev.append(ComedHourlyPricingSensor(
            hass.loop, websession, variable[CONF_SENSOR_TYPE],
            variable[CONF_OFFSET], variable.get(CONF_NAME)))

    async_add_entities(dev, True)


class ComedHourlyPricingSensor(Entity):
    """Implementation of a ComEd Hourly Pricing sensor."""

    def __init__(self, loop, websession, sensor_type, offset, name):
        """Initialize the sensor."""
        self.loop = loop
        self.websession = websession
        if name:
            self._name = name
        else:
            self._name = SENSOR_TYPES[sensor_type][0]
        self.type = sensor_type
        self.offset = offset
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

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
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {ATTR_ATTRIBUTION: CONF_ATTRIBUTION}
        return attrs

    @asyncio.coroutine
    def async_update(self):
        """Get the ComEd Hourly Pricing data from the web service."""
        try:
            if self.type == CONF_FIVE_MINUTE or \
                    self.type == CONF_CURRENT_HOUR_AVERAGE:
                url_string = _RESOURCE
                if self.type == CONF_FIVE_MINUTE:
                    url_string += '?type=5minutefeed'
                else:
                    url_string += '?type=currenthouraverage'

                with async_timeout.timeout(60, loop=self.loop):
                    response = yield from self.websession.get(url_string)
                    # The API responds with MIME type 'text/html'
                    text = yield from response.text()
                    data = json.loads(text)
                    self._state = round(
                        float(data[0]['price']) + self.offset, 2)

            else:
                self._state = STATE_UNKNOWN

        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error("Could not get data from ComEd API: %s", err)
        except (ValueError, KeyError):
            _LOGGER.warning("Could not update status for %s", self.name)
