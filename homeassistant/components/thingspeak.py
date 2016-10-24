"""
A component to submit data to thingspeak
"""
import logging

import voluptuous as vol

from homeassistant.const import (
    EVENT_STATE_CHANGED, CONF_API_KEY, CONF_ID, CONF_WHITELIST,
    STATE_UNAVAILABLE, STATE_UNKNOWN)
from homeassistant.helpers import state as state_helper
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['thingspeak==0.4.0']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'thingspeak'
TIMEOUT = 5

# Validate the config
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Inclusive(CONF_API_KEY): cv.string,
        vol.Inclusive(CONF_ID): cv.int,
        vol.Inclusive(CONF_WHITELIST): cv.string
        }),
    }, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """ Setup the thingspeak environment """
    import thingspeak

    # Read out config values
    conf = config[DOMAIN]
    api_key = conf.get(CONF_API_KEY)
    channel_id = conf.get(CONF_ID)
    entity = conf.get(CONF_WHITELIST)

    try:
        channel = thingspeak.Channel(
            channel_id, api_key=api_key, timeout=TIMEOUT)
        channel.get()
    except:
        _LOGGER.error("Error while accessing the ThingSpeak channel. "
                      "Please check that the channel exists and your "
                      "API key is correct.")
        return False

    def thingspeak_event_listener(event):
        """ Listens for new events and send them to thingspeak """
        state = event.data.get('new_state')
        if state is None or state.state in (
                STATE_UNKNOWN, '', STATE_UNAVAILABLE):
            return
        try:
            if state.entity_id != entity:
                return
            _state = state_helper.state_as_number(state)
        except ValueError:
            return
        try:
            channel.update({'field1': _state})
        except:
            _LOGGER.error(
                'Error while sending value "%s" to Thingspeak',
                _state)

    hass.bus.listen(EVENT_STATE_CHANGED, thingspeak_event_listener)

    return True
