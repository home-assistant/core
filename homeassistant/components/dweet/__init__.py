"""Support for sending data to Dweet.io."""
from datetime import timedelta
import logging

import dweepy
import voluptuous as vol

from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    CONF_NAME,
    CONF_WHITELIST,
    EVENT_STATE_CHANGED,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import state as state_helper
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DOMAIN = "dweet"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=1)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_NAME): cv.string,
                vol.Required(CONF_WHITELIST, default=[]): vol.All(
                    cv.ensure_list, [cv.entity_id]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Dweet.io component."""
    conf = config[DOMAIN]
    name = conf.get(CONF_NAME)
    whitelist = conf.get(CONF_WHITELIST)
    json_body = {}

    def dweet_event_listener(event):
        """Listen for new messages on the bus and sends them to Dweet.io."""
        state = event.data.get("new_state")
        if (
            state is None
            or state.state in (STATE_UNKNOWN, "")
            or state.entity_id not in whitelist
        ):
            return

        try:
            _state = state_helper.state_as_number(state)
        except ValueError:
            _state = state.state

        json_body[state.attributes.get(ATTR_FRIENDLY_NAME)] = _state

        send_data(name, json_body)

    hass.bus.listen(EVENT_STATE_CHANGED, dweet_event_listener)

    return True


@Throttle(MIN_TIME_BETWEEN_UPDATES)
def send_data(name, msg):
    """Send the collected data to Dweet.io."""
    try:
        dweepy.dweet_for(name, msg)
    except dweepy.DweepyError:
        _LOGGER.error("Error saving data to Dweet.io: %s", msg)
