"""
Offer automation trigger based on a schedule.

For more details about this automation rule, please refer to the documentation
at https://home-assistant.io/docs/automation/trigger/#schedule-trigger.


Example config:
---------------
  input_boolean:
    mock_heating:
      name: Mock heating
      initial: off

  automation:
    - alias: 'Heating control'
      trigger:
        platform: schedule
        schedule:
          - "Mon-Wed, Fri: 05:00-07:30, 16:00-22:00"
          - "Thu: 06:00+2h30m, 15:00+7h"
          - "Sat-Sun: 06:00=on, 22:00=off"
      action:
        - service_template: >
          {% if trigger.schedule_state == 'on' %}
            homeassistant.turn_on
          {% else %}
            homeassistant.turn_off
          {% endif %}
            entity_id: input_boolean.mock_heating
"""
import asyncio
import logging

from datetime import datetime, timedelta
import voluptuous as vol

from homeassistant.core import callback, HomeAssistant
from homeassistant.const import CONF_PLATFORM
from homeassistant.helpers.event import async_track_point_in_time
import homeassistant.util.dt as dt

import homeassistant.components.schedule.scheduleparser as sp

PLATFORM = 'schedule'

CONF_SCHEDULE = 'schedule'

_LOGGER = logging.getLogger(__name__)

TRIGGER_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): PLATFORM,
    vol.Required(CONF_SCHEDULE): sp.is_valid_schedule
})


@asyncio.coroutine
def async_trigger(hass: HomeAssistant, config, action):
    """Listen for events based on configuration."""
    schedule = config.get(CONF_SCHEDULE)

    def _schedule_callback(handler, callback_time, now):
        """Schedule a single callback with hass."""
        if callback_time <= now:
            _LOGGER.debug("Running %s for %s as already passed", handler,
                          callback_time)
            return hass.async_run_job(handler, now)
        _LOGGER.debug("Scheduling %s for %s", handler, callback_time)
        return async_track_point_in_time(hass, handler, callback_time)

    def schedule_callbacks(events, now):
        """Schedule callbacks for the list of events plus next midnight."""
        for event_time, _ in events:
            instant = datetime.combine(now.date(), event_time)
            instant = instant.replace(tzinfo=now.tzinfo)
            _schedule_callback(event_callback, instant, now)
        midnight = dt.start_of_local_day(now) + timedelta(days=1)
        return _schedule_callback(midnight_callback, midnight, now)

    @callback
    def midnight_callback(now):
        """Callback at midnight schedules all the events for today."""
        _LOGGER.debug("Received midnight callback")
        events = schedule.get_events_today(now)
        schedule_callbacks(events, now)

    @callback
    def event_callback(now):
        """Trigger action at event time."""
        _LOGGER.debug("Received event callback")
        hass.async_run_job(action, {
            'trigger': {
                'platform': PLATFORM,
                'now': now,
                'schedule_state': schedule.get_current_state(now)
            },
        })

    # Schedule events for the rest of today (i.e. don't include the past)
    now = dt.now()
    events = [event for event in schedule.get_events_today(now)
              if event[0] > now.time()]
    return schedule_callbacks(events, now)
