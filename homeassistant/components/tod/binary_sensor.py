"""Support for representing current time of the day as binary sensors."""
from datetime import datetime, timedelta
import logging

import pytz
import voluptuous as vol

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorEntity
from homeassistant.const import (
    CONF_AFTER,
    CONF_BEFORE,
    CONF_NAME,
    SUN_EVENT_SUNRISE,
    SUN_EVENT_SUNSET,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, event
from homeassistant.helpers.sun import get_astral_event_date, get_astral_event_next
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

ATTR_AFTER = "after"
ATTR_BEFORE = "before"
ATTR_NEXT_UPDATE = "next_update"

CONF_AFTER_OFFSET = "after_offset"
CONF_BEFORE_OFFSET = "before_offset"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_AFTER): vol.Any(cv.time, vol.All(vol.Lower, cv.sun_event)),
        vol.Required(CONF_BEFORE): vol.Any(cv.time, vol.All(vol.Lower, cv.sun_event)),
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_AFTER_OFFSET, default=timedelta(0)): cv.time_period,
        vol.Optional(CONF_BEFORE_OFFSET, default=timedelta(0)): cv.time_period,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the ToD sensors."""
    if hass.config.time_zone is None:
        _LOGGER.error("Timezone is not set in Home Assistant configuration")
        return

    after = config[CONF_AFTER]
    after_offset = config[CONF_AFTER_OFFSET]
    before = config[CONF_BEFORE]
    before_offset = config[CONF_BEFORE_OFFSET]
    name = config[CONF_NAME]
    sensor = TodSensor(name, after, after_offset, before, before_offset)

    async_add_entities([sensor])


def is_sun_event(sun_event):
    """Return true if event is sun event not time."""
    return sun_event in (SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET)


class TodSensor(BinarySensorEntity):
    """Time of the Day Sensor."""

    def __init__(self, name, after, after_offset, before, before_offset):
        """Init the ToD Sensor..."""
        self._name = name
        self._time_before = self._time_after = self._next_update = None
        self._after_offset = after_offset
        self._before_offset = before_offset
        self._before = before
        self._after = after

    @property
    def should_poll(self):
        """Sensor does not need to be polled."""
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def after(self):
        """Return the timestamp for the beginning of the period."""
        return self._time_after

    @property
    def before(self):
        """Return the timestamp for the end of the period."""
        return self._time_before

    @property
    def is_on(self):
        """Return True is sensor is on."""
        if self.after < self.before:
            return self.after <= self.current_datetime < self.before
        return False

    @property
    def current_datetime(self):
        """Return local current datetime according to hass configuration."""
        return dt_util.utcnow()

    @property
    def next_update(self):
        """Return the next update point in the UTC time."""
        return self._next_update

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_AFTER: self.after.astimezone(self.hass.config.time_zone).isoformat(),
            ATTR_BEFORE: self.before.astimezone(self.hass.config.time_zone).isoformat(),
            ATTR_NEXT_UPDATE: self.next_update.astimezone(
                self.hass.config.time_zone
            ).isoformat(),
        }

    def _naive_time_to_utc_datetime(self, naive_time):
        """Convert naive time from config to utc_datetime with current day."""
        # get the current local date from utc time
        current_local_date = self.current_datetime.astimezone(
            self.hass.config.time_zone
        ).date()
        # calculate utc datetime corecponding to local time
        utc_datetime = self.hass.config.time_zone.localize(
            datetime.combine(current_local_date, naive_time)
        ).astimezone(tz=pytz.UTC)
        return utc_datetime

    def _calculate_initial_boudary_time(self):
        """Calculate internal absolute time boundaries."""
        nowutc = self.current_datetime
        # If after value is a sun event instead of absolute time
        if is_sun_event(self._after):
            # Calculate the today's event utc time or
            # if not available take next
            after_event_date = get_astral_event_date(
                self.hass, self._after, nowutc
            ) or get_astral_event_next(self.hass, self._after, nowutc)
        else:
            # Convert local time provided to UTC today
            # datetime.combine(date, time, tzinfo) is not supported
            # in python 3.5. The self._after is provided
            # with hass configured TZ not system wide
            after_event_date = self._naive_time_to_utc_datetime(self._after)

        self._time_after = after_event_date

        # If before value is a sun event instead of absolute time
        if is_sun_event(self._before):
            # Calculate the today's event utc time or  if not available take
            # next
            before_event_date = get_astral_event_date(
                self.hass, self._before, nowutc
            ) or get_astral_event_next(self.hass, self._before, nowutc)
            # Before is earlier than after
            if before_event_date < after_event_date:
                # Take next day for before
                before_event_date = get_astral_event_next(
                    self.hass, self._before, after_event_date
                )
        else:
            # Convert local time provided to UTC today, see above
            before_event_date = self._naive_time_to_utc_datetime(self._before)

            # It is safe to add timedelta days=1 to UTC as there is no DST
            if before_event_date < after_event_date + self._after_offset:
                before_event_date += timedelta(days=1)

        self._time_before = before_event_date

        # We are calculating the _time_after value assuming that it will happen today
        # But that is not always true, e.g. after 23:00, before 12:00 and now is 10:00
        # If _time_before and _time_after are ahead of current_datetime:
        # _time_before is set to 12:00 next day
        # _time_after is set to 23:00 today
        # current_datetime is set to 10:00 today
        if (
            self._time_after > self.current_datetime
            and self._time_before > self.current_datetime + timedelta(days=1)
        ):
            # remove one day from _time_before and _time_after
            self._time_after -= timedelta(days=1)
            self._time_before -= timedelta(days=1)

        # Add offset to utc boundaries according to the configuration
        self._time_after += self._after_offset
        self._time_before += self._before_offset

    def _turn_to_next_day(self):
        """Turn to to the next day."""
        if is_sun_event(self._after):
            self._time_after = get_astral_event_next(
                self.hass, self._after, self._time_after - self._after_offset
            )
            self._time_after += self._after_offset
        else:
            # Offset is already there
            self._time_after += timedelta(days=1)

        if is_sun_event(self._before):
            self._time_before = get_astral_event_next(
                self.hass, self._before, self._time_before - self._before_offset
            )
            self._time_before += self._before_offset
        else:
            # Offset is already there
            self._time_before += timedelta(days=1)

    async def async_added_to_hass(self):
        """Call when entity about to be added to Home Assistant."""
        self._calculate_initial_boudary_time()
        self._calculate_next_update()
        self._point_in_time_listener(dt_util.now())

    def _calculate_next_update(self):
        """Datetime when the next update to the state."""
        now = self.current_datetime
        if now < self.after:
            self._next_update = self.after
            return
        if now < self.before:
            self._next_update = self.before
            return
        self._turn_to_next_day()
        self._next_update = self.after

    @callback
    def _point_in_time_listener(self, now):
        """Run when the state of the sensor should be updated."""
        self._calculate_next_update()
        self.async_write_ha_state()

        event.async_track_point_in_utc_time(
            self.hass, self._point_in_time_listener, self.next_update
        )
