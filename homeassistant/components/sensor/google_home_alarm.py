"""
Sensor for retrieving latest alarm from Google Home.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.google_home_alarm/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.const import CONF_HOST, CONF_MONITORED_CONDITIONS,
                                CONF_DISPLAY_OPTIONS
import homeassistant.util.dt as dt_util

REQUIREMENTS = ['ghlocalapi==0.1.0']

TIME_STR_FORMAT = '%H:%M'

CONF_SHOW_TIMERS = 'show_timers'

ICON = 'mdi:alarm'

SENSOR_TYPE_TIMER = 'timer'
SENSOR_TYPE_ALARM = 'alarm'

SENSOR_TYPES = {
    SENSOR_TYPE_TIMER : "Timer",
    SENSOR_TYPE_ALARM : "Alarm",
}

DISPLAY_TYPES = {
    'time': 'Time',
    'date': 'Date',
    'date_time': 'Date & Time',
    'time_date': 'Time & Date',
    'beat': 'Internet Time',
    'time_utc': 'Time (UTC)',
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_SHOW_TIMERS, default=True): cv.boolean,
    vol.Optional(CONF_MONITORED_CONDITIONS, default=['alarm', 'timer']): 
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_DISPLAY_OPTIONS, default='time'): vol.In(DISPLAY_TYPES)
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
    for condition in config.get(CONF_MONITORED_CONDITIONS):
        device = GoogleHomeAlarmSensor(hass,
                                       name,
                                       host,
                                       condition,
                                       config.get(CONF_DISPLAY_OPTIONS))
        await device.async_update()
        entities.append(device)

    async_add_entities(entities)


class GoogleHomeAlarmSensor(Entity):
    """Representation of a Google Home Alarm Sensor."""

    def __init__(self, hass, name, host, condition, type):
        """Initialize the Google Home Alarm sensor."""
        from ghlocalapi.alarms import Alarms

        self._name = "{} {}".format(name, SENSOR_TYPES[condition])
        self._state = None
        self.type = type
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

            time = dt_util.as_local(time_date).strftime(TIME_STR_FORMAT)
            time_utc = time_date.strftime(TIME_STR_FORMAT)
            date = dt_util.as_local(time_date).date().isoformat()

            # Calculate Swatch Internet Time.
            time_bmt = time_date + timedelta(hours=1)
            d = timedelta(
                hours=time_bmt.hour, minutes=time_bmt.minute,
                seconds=time_bmt.second, microseconds=time_bmt.microsecond)
            beat = int((d.seconds + d.microseconds / 1000000.0) / 86.4)

            if self.type == 'time':
                self._state = time
            elif self.type == 'date':
                self._state = date
            elif self.type == 'date_time':
                self._state = '{}, {}'.format(date, time)
            elif self.type == 'time_date':
                self._state = '{}, {}'.format(time, date)
            elif self.type == 'time_utc':
                self._state = time_utc
            elif self.type == 'beat':
                self._state = '@{0:03d}'.format(beat)
