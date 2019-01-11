"""
Support for showing the binary sensors represending current time of the day.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.tod/
"""
import logging
from datetime import timedelta, datetime,date
import pytz

import voluptuous as vol

from homeassistant.helpers.entity import (Entity, async_generate_entity_id)
from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, ENTITY_ID_FORMAT
from homeassistant.core import callback
from homeassistant.const import (CONF_SENSORS, CONF_AFTER, CONF_BEFORE, ATTR_FRIENDLY_NAME, 
    ATTR_ENTITY_ID, SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET)
from homeassistant.helpers.event import (
    async_track_point_in_utc_time, async_track_utc_time_change)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.sun import (
    get_astral_location, get_astral_event_date, get_astral_event_next)
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

CONF_AFTER_OFFSET = 'after_offset'
CONF_BEFORE_OFFSET = 'before_offset'


utc = pytz.UTC

SENSOR_SCHEMA = vol.Schema({
    vol.Required(CONF_AFTER): vol.Any(cv.time, vol.All(vol.Lower, vol.Any(cv.sun_event))),
    vol.Optional(CONF_AFTER_OFFSET, default=timedelta()): cv.time_period,
    vol.Required(CONF_BEFORE): vol.Any(cv.time, vol.All(vol.Lower, vol.Any(cv.sun_event))),
    vol.Optional(CONF_BEFORE_OFFSET, default=timedelta()): cv.time_period,
    vol.Optional(ATTR_FRIENDLY_NAME): cv.string,
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    # vol.Optional(CONF_DELAY_ON):
    #     vol.All(cv.time_period, cv.positive_timedelta),
    # vol.Optional(CONF_DELAY_OFF):
    #     vol.All(cv.time_period, cv.positive_timedelta),
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SENSORS): vol.Schema({cv.slug: SENSOR_SCHEMA}),
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the ToD sensors."""
    if hass.config.time_zone is None:
        _LOGGER.error("Timezone is not set in Home Assistant configuration")
        return False

    _LOGGER.error("Config: %s", config)
    sensors = []
    for device, device_config in config[CONF_SENSORS].items():
        sensors.append(
            TodSensor(
                hass, device, device_config
            )
        )

    if not sensors:
        _LOGGER.error("No sensors added")
        return False

    async_add_entities(sensors)
    return True


class TodSensor(Entity):
    """Time of the Day Sensor."""
    def __init__(self, hass, sensor_name, config):
        self._name = sensor_name
        self._state = False
        self.hass = hass
        self._config = config
        self._sunrising = None
        self._sunsetting = None
        self._next_sunrising = None
        self._next_sunsetting = None
        
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, f'tod_{sensor_name}', hass=hass)
        after = self._config[CONF_AFTER]
        before = self._config[CONF_BEFORE]
        after_offset = self._config[CONF_AFTER_OFFSET]
        before_offset = self._config[CONF_BEFORE_OFFSET]
        
        if after in [SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET]:
            self._after = get_astral_event_date(
                self.hass, after, dt_util.utcnow())
        else:
            self._after = dt_util.as_utc(datetime.combine(datetime.now(), self._config[CONF_AFTER]))
        
        self._after += after_offset

        if before in [SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET]:
            self._before = get_astral_event_date(
                self.hass, before, dt_util.utcnow())
            self._before += before_offset
            if self._after > self.before:
               self._before = get_astral_event_date(
                self.hass, before, dt_util.utcnow() + timedelta(days=1))
        else:
            self._before = dt_util.as_utc(datetime.combine(datetime.now(), self._config[CONF_BEFORE]))
            self._before += before_offset
            if self.after > self.before:
                self._before += timedelta(days=1)

        
    async def async_added_to_hass(self):
        """Register callbacks."""
        self.point_in_time_listener(dt_util.utcnow())
    
    # @property
    # def unique_id(self) -> str:
    #     """Return a unique ID."""
    #     return None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def after(self):
        """Return the timestamp for the begining of the period"""
        return self._after

    @property
    def before(self):
        """Return the timestamp for the end of the period"""
        return self._before

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.after < dt_util.as_utc(datetime.now()) < self.before
        
    @property
    def next_change(self):
        return dt_util.utcnow()
    
    @property
    def state_attributes(self):
        """Return the state attributes of the sun."""
        return {
            CONF_AFTER: self.after.isoformat(),
            CONF_BEFORE: self.before.isoformat(),
            'sunrise': self._sunrising.isoformat(),
            'sunset': self._sunsetting.isoformat(),
            'next_sunrise': self._next_sunrising.isoformat(),
            'next_sunsetting': self._next_sunsetting.isoformat(),
            'NOW': dt_util.as_utc(datetime.now()).isoformat()
        }


    @callback
    def update_as_of(self, utc_point_in_time):
        """Update the sun events."""
        self._sunrising = get_astral_event_date(
            self.hass, SUN_EVENT_SUNRISE, utc_point_in_time)
        self._sunsetting = get_astral_event_date(
            self.hass, SUN_EVENT_SUNSET, utc_point_in_time)
        self._next_sunrising = get_astral_event_next(
            self.hass, SUN_EVENT_SUNRISE, utc_point_in_time)
        self._next_sunsetting = get_astral_event_next(
            self.hass, SUN_EVENT_SUNSET, utc_point_in_time)
    
    @callback
    def point_in_time_listener(self, now):
        """Run when the state of the sun has changed."""
        self.update_as_of(now)
        self.async_schedule_update_ha_state()

        # Schedule next update at next_change+1 second so sun state has changed
        async_track_point_in_utc_time(
            self.hass, self.point_in_time_listener,
            self.next_change + timedelta(seconds=1))
