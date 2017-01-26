"""
A component to submit data to thingspeak.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/thingspeak/
"""
import logging

from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant.const import (
    CONF_API_KEY, CONF_ID, CONF_WHITELIST, STATE_UNAVAILABLE, STATE_UNKNOWN)
from homeassistant.helpers import state as state_helper
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.event as event

REQUIREMENTS = ['thingspeak==0.4.0']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'thingspeak'

TIMEOUT = 5

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_ID): int,
        vol.Required(CONF_WHITELIST): cv.string
        }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Thingspeak environment for multiply channels."""
    import thingspeak

    def thingspeak_listener(entity_id, old_state, new_state):
        """Listen for new events and send them to thingspeak."""
        if new_state is None or new_state.state in (
                STATE_UNKNOWN, '', STATE_UNAVAILABLE):
            return
        try:
            _state = state_helper.state_as_number(new_state)
        except ValueError:
            return
        try:
            _channel = entities[entity_id]
            _channel.update({'api_key': _channel.api_key, 'field1': _state})
        except RequestException:
            _LOGGER.error("Error while sending value %s to Thingspeak "
                          "channel_id: %s", _state, _channel.channel_id)
    entities = {}

    for object_id, conf in config.items():
        if not conf:
            continue
        # checking for "thingspeak 1:" "THIingspeak 2:"
        if object_id[:len(DOMAIN)].lower() != DOMAIN:
            continue
        # info to create the thingspeak channel
        api_key = conf.get(CONF_API_KEY)
        channel_id = conf.get(CONF_ID)
        entity = conf.get(CONF_WHITELIST)
        try:
            channel = thingspeak.Channel(
                channel_id, api_key=api_key, timeout=TIMEOUT)
            channel.get()
        except RequestException:
            _LOGGER.error("Error while accessing the ThingSpeak channel_id:%s"
                          "Please check that the channel exists and your "
                          "API key is correct.", channel_id)
            # go to the next sensor
            continue
        entities[entity] = channel
        event.track_state_change(hass, entity, thingspeak_listener)

    # return False if all channels are errored
    return entities != {}
