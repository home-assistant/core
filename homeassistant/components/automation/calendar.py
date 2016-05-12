"""
Offer trigger state for calendar events with offset abilities.
"""
import voluptuous as vol
import functools as fc
from datetime import timedelta
import logging

from homeassistant.const import CONF_PLATFORM
from homeassistant.util import dt
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import track_time_change

# how to get dependencie of google_calendar or icloud_calendar?
CONF_ENTITY_ID = 'entity_id'
CONF_OFFSET = 'offset'

TRIGGER_SCHEMA = vol.All(vol.Schema({
    vol.Required(CONF_PLATFORM): 'calendar',
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Required(CONF_OFFSET, default=timedelta(0)): cv.time_period,
}))

_LOGGER = logging.getLogger(__name__)


def trigger(hass, config, action):
    """Listen for time change."""
    entity_id = config.get(CONF_ENTITY_ID)
    offset = config.get(CONF_OFFSET)
   
    @fc.wraps(action)
    def calendar_automation_listener(event):
        """The listener that listens for time changes."""
        entity_state = hass.states.get(entity_id)
        if not entity_state:
            return

        start = entity_state.attributes.get('start_time', None)
        if not start:
            return

        now = dt.now(start.tzinfo)
        now = now.replace(second=0, microsecond=0)
        time = int((start + offset - now).total_seconds())
        if time < 60 and time >= 0:
            action({
                'trigger': {
                    'platform': 'calendar',
                    'entity_id': entity_id,
                    'offset': offset
                }
            })

    # run every minute
    track_time_change(hass, calendar_automation_listener, second=0)
    return True
