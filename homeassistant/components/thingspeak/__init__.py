"""Support for submitting data to Thingspeak."""

import logging

import probatio
from requests.exceptions import RequestException
import thingspeak

from homeassistant.const import (
    CONF_API_KEY,
    CONF_ID,
    CONF_WHITELIST,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant
from homeassistant.helpers import config_validation as cv, state as state_helper
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "thingspeak"

TIMEOUT = 5

CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: probatio.Schema(
            {
                probatio.Required(probatio.Secret(CONF_API_KEY)): cv.string,
                probatio.Required(CONF_ID): int,
                probatio.Required(CONF_WHITELIST): cv.string,
            }
        )
    },
    extra=probatio.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Thingspeak environment."""
    conf = config[DOMAIN]
    api_key = conf.get(CONF_API_KEY)
    channel_id = conf.get(CONF_ID)
    entity = conf.get(CONF_WHITELIST)

    channel = thingspeak.Channel(channel_id, api_key=api_key, timeout=TIMEOUT)
    try:
        await hass.async_add_executor_job(channel.get)
    except RequestException:
        _LOGGER.error(
            "Error while accessing the ThingSpeak channel. "
            "Please check that the channel exists and your API key is correct"
        )
        return False

    def thingspeak_listener(event: Event[EventStateChangedData]):
        """Listen for new events and send them to Thingspeak."""
        new_state = event.data["new_state"]
        if new_state is None or new_state.state in (
            STATE_UNKNOWN,
            "",
            STATE_UNAVAILABLE,
        ):
            return
        try:
            if new_state.entity_id != entity:
                return
            _state = state_helper.state_as_number(new_state)
        except ValueError:
            return
        try:
            channel.update({"field1": _state})
        except RequestException:
            _LOGGER.error("Error while sending value '%s' to Thingspeak", _state)

    async_track_state_change_event(hass, entity, thingspeak_listener)

    return True
