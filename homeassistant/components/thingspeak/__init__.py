"""Support for submitting data to Thingspeak."""
import logging

from requests.exceptions import RequestException
import thingspeak
import voluptuous as vol

from homeassistant.const import (
    CONF_API_KEY,
    CONF_ID,
    CONF_WHITELIST,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import event, state as state_helper
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "thingspeak"

TIMEOUT = 5

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_API_KEY): cv.string,
                vol.Required(CONF_ID): int,
                vol.Required(CONF_WHITELIST): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Thingspeak environment."""
    conf = config[DOMAIN]
    api_key = conf.get(CONF_API_KEY)
    channel_id = conf.get(CONF_ID)
    entity = conf.get(CONF_WHITELIST)

    try:
        channel = thingspeak.Channel(channel_id, api_key=api_key, timeout=TIMEOUT)
        channel.get()
    except RequestException:
        _LOGGER.error(
            "Error while accessing the ThingSpeak channel. "
            "Please check that the channel exists and your API key is correct"
        )
        return False

    def thingspeak_listener(entity_id, old_state, new_state):
        """Listen for new events and send them to Thingspeak."""
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

    event.track_state_change(hass, entity, thingspeak_listener)

    return True
