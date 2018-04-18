"""
Sensor providing state changes based on a schedule.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.state_schedule/

Example config
--------------
  sensor:
    platform: state_schedule
    name: "heating schedule"
    schedule:
      - "Mon-Fri: 11:00-17:00"
      - "Sat, Sun: 12:05+15s"

  input_boolean:
    mock_heating:
        name: Mock heating
        initial: off

  automation:
    - alias: 'Track heating schedule'
      trigger:
        platform: state
        entity_id: sensor.heating_schedule
      action:
        service_template: >
          {% if is_state('sensor.heating_schedule', 'on') %}
            homeassistant.turn_on
          {% else %}
            homeassistant.turn_off
          {% endif %}
        entity_id: input_boolean.mock_heating
"""
import asyncio
from datetime import datetime, timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.components.schedule.scheduleparser as sp
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_point_in_time
import homeassistant.util.dt as dt

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'State Schedule sensor'

ATTR_SCHEDULE = 'schedule'
ATTR_LAST_CHANGED = 'last state change'
ATTR_LAST_UPDATED = 'last updated'
ATTR_NEXT_UPDATE = 'next update'

CONF_SCHEDULE = 'schedule'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_SCHEDULE): sp.is_valid_schedule
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices,
                         discovery_info=None):
    """Set up the Statistics sensor."""
    name = config.get(CONF_NAME)
    schedule = config.get(CONF_SCHEDULE)

    sensor = StateScheduleSensor(hass, name, schedule)
    sensor.add_callback()
    async_add_devices([sensor], True)
    return True


class StateScheduleSensor(Entity):
    """Implementation of a sensor which changes state based on a schedule."""

    def __init__(self, hass, name, schedule):
        """Initialize the sensor."""
        self._hass = hass
        self._name = name
        self._schedule = schedule
        self._update_internal_state(dt.now())

    def _update_internal_state(self, time_date):
        """Update the state and calc the next event time."""
        event = self._schedule.get_latest_event(time_date)
        self._last_updated = time_date
        self._last_changed = event[0]
        self._state = event[1]
        next_event = self._schedule.get_next_event_today(time_date)
        if next_event:
            local_time = next_event[0].replace(tzinfo=time_date.tzinfo)
            self._next_update = datetime.combine(time_date, local_time)
        else:
            self._next_update = dt.start_of_local_day(time_date) + \
                                timedelta(days=1)

    def add_callback(self):
        """Set the next callback from Hass."""
        async_track_point_in_time(self._hass,
                                  self.point_in_time_listener,
                                  self._next_update)

    @callback
    def point_in_time_listener(self, time_date):
        """Callback from Hass when we hit the next update time."""
        self._update_internal_state(time_date)
        self.async_schedule_update_ha_state()
        self.add_callback()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        state = {
            ATTR_SCHEDULE: self._schedule.text,
            ATTR_LAST_CHANGED: self._last_changed.isoformat(),
            ATTR_LAST_UPDATED: self._last_updated.isoformat(),
            ATTR_NEXT_UPDATE: self._next_update.isoformat()
        }
        return state
