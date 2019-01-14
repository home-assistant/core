"""
Support for showing the binary sensors represending current time of the day.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.tod/

"""
from datetime import datetime, timedelta
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    ENTITY_ID_FORMAT, PLATFORM_SCHEMA)
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME, CONF_AFTER, CONF_BEFORE, CONF_SENSORS,
    STATE_OFF, STATE_ON, SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity, async_generate_entity_id
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.sun import (
    get_astral_event_date, get_astral_event_next)
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

CONF_AFTER_OFFSET = 'after_offset'
CONF_BEFORE_OFFSET = 'before_offset'

ATTR_NEXT_UPDATE = 'next_update'


SENSOR_SCHEMA = vol.Schema({
    vol.Required(CONF_AFTER): vol.Any(cv.time, vol.All(
        vol.Lower, vol.Any(cv.sun_event))),
    vol.Optional(CONF_AFTER_OFFSET, default=timedelta(0)): cv.time_period,
    vol.Required(CONF_BEFORE): vol.Any(cv.time, vol.All(
        vol.Lower, vol.Any(cv.sun_event))),
    vol.Optional(CONF_BEFORE_OFFSET, default=timedelta(0)): cv.time_period,
    vol.Optional(ATTR_FRIENDLY_NAME): cv.string,
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
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

    sensors = []
    for device, device_config in config[CONF_SENSORS].items():
        after = device_config[CONF_AFTER]
        after_offset = device_config[CONF_AFTER_OFFSET]
        before = device_config[CONF_BEFORE]
        before_offset = device_config[CONF_BEFORE_OFFSET]
        sensors.append(
            TodSensor(
                hass, device, after, after_offset, before, before_offset
            )
        )

    if not sensors:
        _LOGGER.error("No sensors added")
        return

    async_add_entities(sensors)
    return


def is_sun_event(event):
    """Return true if event is sun event not time."""
    return event in (SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET)


class TodSensor(Entity):
    """Time of the Day Sensor."""

    def __init__(self, hass, sensor_name, after, after_offset,
                 before, before_offset):
        """Init the ToD Sensor..."""
        self._name = sensor_name
        self._state = None
        self.hass = hass

        self._time_before = None
        self._time_after = None
        self._after_offset = after_offset
        self._before_offset = before_offset
        self._before = before
        self._after = after

        self._sunrising = None
        self._sunsetting = None
        self._next_sunrising = None
        self._next_sunsetting = None

        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, 'tod_{}'.format(sensor_name), hass=hass)
        self._calculate_initial_boudary_time()

    def _calculate_initial_boudary_time(self):
        """Calculate internal absolute time boudaries."""
        today = self.current_datetime

        if is_sun_event(self._after):
            after_event_date = \
                get_astral_event_date(
                    self.hass, self._after, dt_util.as_utc(today)) or \
                get_astral_event_next(
                    self.hass, self._after, dt_util.as_utc(today))
            if after_event_date:
                self._time_after = dt_util.as_local(after_event_date)
            else:
                _LOGGER.error("After event date for %s unknown", self._after)
        else:
            self._time_after = datetime.combine(
                today.date(), self._after, tzinfo=self.hass.config.time_zone)

        if is_sun_event(self._before):
            before_event_date = get_astral_event_next(
                self.hass, self._before, dt_util.as_utc(self._time_after))
            if before_event_date:
                self._time_before = dt_util.as_local(before_event_date)
            else:
                _LOGGER.error("Before event date for %s unknown", self._before)
        else:
            self._time_before = datetime.combine(
                today.date(), self._before, tzinfo=self.hass.config.time_zone)
            if self._time_after > self._time_before:
                self._time_before += timedelta(days=1)

        self._time_after += self._after_offset
        self._time_before += self._before_offset

    def _turn_to_next_day(self):
        """Turn to to the next day."""
        if is_sun_event(self._after):
            self._time_after = dt_util.as_local(get_astral_event_next(
                self.hass, self._after, dt_util.as_utc(
                    self._time_after - self._after_offset)))
            self._time_after += self._after_offset
        else:
            # offset is already there
            self._time_after += timedelta(days=1)

        if is_sun_event(self._before):
            self._time_before = dt_util.as_local(get_astral_event_next(
                self.hass, self._before, dt_util.as_utc(
                    self._time_before - self._before_offset)))
            self._time_before += self._before_offset
        else:
            self._time_before += timedelta(days=1)

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.point_in_time_listener(dt_util.now())

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def after(self):
        """Return the timestamp for the begining of the period."""
        return self._time_after

    @property
    def before(self):
        """Return the timestamp for the end of the period."""
        return self._time_before

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.after < self.before:
            if self.after <= self.current_datetime < self.before:
                return STATE_ON
        return STATE_OFF

    @property
    def current_datetime(self):
        """Return local current datetime according to hass configuration."""
        return dt_util.now(self.hass.config.time_zone)

    @property
    def next_change(self):
        """Datetime when the next change to the state is."""
        now = self.current_datetime
        if now < self.after:
            return self.after
        if now < self.before:
            return self.before

        self._turn_to_next_day()
        return self.after

    @property
    def state_attributes(self):
        """Return the state attributes of the sun."""
        return {
            CONF_AFTER: self.after.isoformat(),
            CONF_BEFORE: self.before.isoformat(),
            ATTR_NEXT_UPDATE: self.next_change.isoformat()
        }

    @callback
    def point_in_time_listener(self, now):
        """Run when the state of the sun has changed."""
        self.async_schedule_update_ha_state()

        async_track_point_in_time(
            self.hass, self.point_in_time_listener,
            self.next_change)
