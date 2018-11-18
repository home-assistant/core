"""
Sensor for retrieving latest alarm from Google Home.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.gitlab_ci/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.const import CONF_HOST

REQUIREMENTS = ['ghlocalapi==0.1.0']

_LOGGER = logging.getLogger(__name__)

CONF_SHOW_TIMERS = 'show_timers'

ICON = 'mdi:alarm'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_SHOW_TIMERS, default=True): cv.boolean
})

async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    from ghlocalapi.device_info import DeviceInfo

    host = config.get(CONF_HOST)    

    devinfo = DeviceInfo(hass.loop, async_get_clientsession(hass), host)
    await devinfo.get_device_info()

    name = devinfo.device_info['name']

    async_add_entities([GoogleHomeAlarmSensor(hass, name, host)])
 


class GoogleHomeAlarmSensor(Entity):
    def __init__(self, hass, name, host):
        from ghlocalapi.alarms import Alarms

        self._name = name
        self._alarms = None
        self._state = ""
        self._alarmsapi = Alarms(hass.loop, async_get_clientsession(hass), host)

    @property
    def name(self):
        return self._name
    
    @property
    def state(self):
        return self._state

    async def update(self):
        await self._alarmsapi.get_alarms()
        self._alarms = self._alarmsapi.alarms
        self._state = "Ok"

        

    
