"""
Sensor for retrieving latest alarm from Google Home.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.google_home_alarm/
"""
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.const import CONF_HOST
import homeassistant.util.dt as dt_util

REQUIREMENTS = ['ghlocalapi==0.1.0']

ICON = 'mdi:alarm'

SENSOR_TYPES = {
    'timer': "Timer",
    'alarm': "Alarm",
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Google Home Alarm platform."""
    from ghlocalapi.device_info import DeviceInfo

    host = config.get(CONF_HOST)

    devinfo = DeviceInfo(hass.loop, async_get_clientsession(hass), host)
    await devinfo.get_device_info()
    name = devinfo.device_info['name']

    entities = []
    for condition in SENSOR_TYPES:
        device = GoogleHomeAlarmSensor(hass,
                                       name,
                                       host,
                                       condition)
        await device.async_update()
        entities.append(device)

    async_add_entities(entities)


class GoogleHomeAlarmSensor(Entity):
    """Representation of a Google Home Alarm Sensor."""

    def __init__(self, hass, name, host, condition):
        """Initialize the Google Home Alarm sensor."""
        from ghlocalapi.alarms import Alarms

        self._name = "{} {}".format(name, SENSOR_TYPES[condition])
        self._state = None
        self._alarmsapi = Alarms(hass.loop,
                                 async_get_clientsession(hass),
                                 host)
        self._condition = condition
        self._available = True

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def icon(self):
        """Return the icon."""
        return 'mdi:alarm'

    @property
    def available(self):
        """Return the availability state."""
        return self._available

    @property
    def state(self):
        """Return the state."""
        return self._state

    async def async_update(self):
        """Get the latest data and updates the state."""
        await self._alarmsapi.get_alarms()
        data = self._alarmsapi.alarms[self._condition]
        if not data:
            self._available = False
        else:
            self._available = True
            time_date = dt_util.utc_from_timestamp(min(
                element['fire_time'] for element in data) / 1000)
            self._state = time_date.isoformat()
