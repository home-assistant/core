"""Support for showing the date and the time."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_DISPLAY_OPTIONS
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.helpers.event import async_track_point_in_utc_time

_LOGGER = logging.getLogger(__name__)

TIME_STR_FORMAT = '%H:%M'

OPTION_TYPES = {
    'time': 'Time',
    'date': 'Date',
    'date_time': 'Date & Time',
    'date_time_iso': 'Date & Time ISO',
    'time_date': 'Time & Date',
    'beat': 'Internet Time',
    'time_utc': 'Time (UTC)',
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DISPLAY_OPTIONS, default=['time']):
        vol.All(cv.ensure_list, [vol.In(OPTION_TYPES)]),
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Time and Date sensor."""
    if hass.config.time_zone is None:
        _LOGGER.error("Timezone is not set in Home Assistant configuration")
        return False

    devices = []
    for variable in config[CONF_DISPLAY_OPTIONS]:
        device = TimeDateSensor(hass, variable)
        async_track_point_in_utc_time(
            hass, device.point_in_time_listener, device.get_next_interval())
        devices.append(device)

    async_add_entities(devices, True)


class TimeDateSensor(Entity):
    """Implementation of a Time and Date sensor."""

    def __init__(self, hass, option_type):
        """Initialize the sensor."""
        self._name = OPTION_TYPES[option_type]
        self.type = option_type
        self._state = None
        self.hass = hass

        self._update_internal_state(dt_util.utcnow())

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if 'date' in self.type and 'time' in self.type:
            return 'mdi:calendar-clock'
        if 'date' in self.type:
            return 'mdi:calendar'
        return 'mdi:clock'

    def get_next_interval(self, now=None):
        """Compute next time an update should occur."""
        if now is None:
            now = dt_util.utcnow()
        if self.type == 'date':
            now = dt_util.start_of_local_day(dt_util.as_local(now))
            return now + timedelta(seconds=86400)
        if self.type == 'beat':
            interval = 86.4
        else:
            interval = 60
        timestamp = int(dt_util.as_timestamp(now))
        delta = interval - (timestamp % interval)
        return now + timedelta(seconds=delta)

    def _update_internal_state(self, time_date):
        time = dt_util.as_local(time_date).strftime(TIME_STR_FORMAT)
        time_utc = time_date.strftime(TIME_STR_FORMAT)
        date = dt_util.as_local(time_date).date().isoformat()

        # Calculate Swatch Internet Time.
        time_bmt = time_date + timedelta(hours=1)
        delta = timedelta(
            hours=time_bmt.hour, minutes=time_bmt.minute,
            seconds=time_bmt.second, microseconds=time_bmt.microsecond)
        beat = int((delta.seconds + delta.microseconds / 1000000.0) / 86.4)

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
        elif self.type == 'date_time_iso':
            self._state = dt_util.parse_datetime(
                '{} {}'.format(date, time)).isoformat()

    @callback
    def point_in_time_listener(self, time_date):
        """Get the latest data and update state."""
        self._update_internal_state(time_date)
        self.async_schedule_update_ha_state()
        async_track_point_in_utc_time(
            self.hass, self.point_in_time_listener, self.get_next_interval())
