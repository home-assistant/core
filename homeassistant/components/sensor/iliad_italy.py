"""
Sensor to get Iliad Italy personal data.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.iliad_italy/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util

REQUIREMENTS = ['aioiliad==0.1.1']

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by Iliad Italy"

ICON = 'mdi:phone'

SCAN_INTERVAL = timedelta(minutes=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})


async def async_setup_platform(
        hass, conf, async_add_entities, discovery_info=None):
    """Set up the Iliad Italy sensor platform."""
    from aioiliad import Iliad
    iliad = Iliad(conf[CONF_USERNAME], conf[CONF_PASSWORD],
                  async_get_clientsession(hass), hass.loop)
    await iliad.login()

    if not iliad.is_logged_in():
        _LOGGER.error("Check username and password")
        return

    async_add_entities([IliadSensor(iliad)], True)


class IliadSensor(Entity):
    """Representation of a Iliad Italy Sensor."""

    def __init__(self, iliad):
        """Initialize the Iliad Italy sensor."""
        from aioiliad.IliadData import IliadData
        self._iliad = iliad
        self._iliaddata = IliadData(self._iliad)
        self._data = None
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Iliad {}".format(self._data['info']['utente'])

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
        """Return the unit of measurement of the sensor."""
        return '€'

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        attr = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            'next_renewal':
                dt_util.utc_from_timestamp(
                    self._data['info']['rinnovo']).isoformat(),
            'italy_sent_sms': self._data['italy']['sms'],
            'italy_over_plan_sms': self._data['italy']['sms_extra'],
            'italy_sent_mms': self._data['italy']['mms'],
            'italy_over_plan_mms': self._data['italy']['mms_extra'],
            'italy_calls_seconds': self._data['italy']['chiamate'],
            'italy_over_plan_calls': self._data['italy']['chiamate_extra'],
            'italy_data': self._data['italy']['internet'],
            'italy_data_max': self._data['italy']['internet_max'],
            'italy_data_over_plan': self._data['italy']['internet_over'],

            'abroad_sent_sms': self._data['estero']['sms'],
            'abroad_over_plan_sms': self._data['estero']['sms_extra'],
            'abroad_sent_mms': self._data['estero']['mms'],
            'abroad_over_plan_mms': self._data['estero']['mms_extra'],
            'abroad_calls_seconds': self._data['estero']['chiamate'],
            'abroad_over_plan_calls': self._data['estero']['chiamate_extra'],
            'abroad_data': self._data['estero']['internet'],
            'abroad_data_max': self._data['estero']['internet_max'],
            'abroad_data_over_plan': self._data['estero']['internet_over'],
        }
        return attr

    async def async_update(self):
        """Update device state."""
        await self._iliaddata.update()
        self._data = {
            'italy': self._iliaddata.get_italy(),
            'estero': self._iliaddata.get_estero(),
            'info': self._iliaddata.get_general_info()
        }
        self._state = self._data['info']['credito'].replace('€', '')
