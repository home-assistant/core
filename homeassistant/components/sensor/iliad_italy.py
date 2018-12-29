"""
Sensor to get Iliad Italy personal data.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.iliad_italy/
"""
import logging
from datetime import timedelta, datetime

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.helpers.aiohttp_client import async_get_clientsession

REQUIREMENTS = ['aioiliad==0.1.1']

_LOGGER = logging.getLogger(__name__)

ICON = 'mdi:phone'

SCAN_INTERVAL = timedelta(hours=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string
})


async def async_setup_platform(
        hass, conf, async_add_entities, discovery_info=None):
    """Set up the Iliad Italy platform."""
    from aioiliad import Iliad
    iliad = Iliad(conf[CONF_USERNAME], conf[CONF_PASSWORD], async_get_clientsession(hass), hass.loop)
    await iliad.login()
    async_add_entities([IliadSensor(iliad)], True)


class IliadSensor(Entity):
    """Representation of a IliadItaly Sensor."""

    def __init__(self, iliad):
        """Initialize the IliadItaly sensor."""
        from aioiliad.IliadData import IliadData
        self._iliad = iliad
        self._iliad
        self._iliaddata = IliadData(self._iliad)
        self._data = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Iliad"

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICON

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state
    
    @property
    def unit_of_measurement(self):
        return "€"

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        attr = {
        }
        return self._data

    async def async_update(self):
        """Update device state."""
        await self._iliaddata.update()
        self._data = {
            'italy': self._iliaddata.get_italy(),
            'estero': self._iliaddata.get_estero(),
            'info': self._iliaddata.get_general_info()
        }
        self._state = self._data['info']['credito'].replace('€', '')
