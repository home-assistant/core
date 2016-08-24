"""
Support for sending data to Logentries webhook endpoint.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/logentries/
"""
import json
import logging
import requests

import voluptuous as vol

from homeassistant.const import (CONF_TOKEN, EVENT_STATE_CHANGED)
from homeassistant.helpers import state as state_helper
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'logentries'

DEFAULT_HOST = 'https://webhook.logentries.com/noformat/logs/'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_TOKEN): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Setup the Logentries component."""
    conf = config[DOMAIN]
    token = conf.get(CONF_TOKEN)
    le_wh = '{}{}'.format(DEFAULT_HOST, token)

    def logentries_event_listener(event):
        """Listen for new messages on the bus and sends them to Logentries."""
        state = event.data.get('new_state')
        if state is None:
            return
        try:
            _state = state_helper.state_as_number(state)
        except ValueError:
            _state = state.state
        json_body = [
            {
                'domain': state.domain,
                'entity_id': state.object_id,
                'attributes': dict(state.attributes),
                'time': str(event.time_fired),
                'value': _state,
            }
        ]
        try:
            payload = {"host": le_wh,
                       "event": json_body}
            requests.post(le_wh, data=json.dumps(payload), timeout=10)
        except requests.exceptions.RequestException as error:
            _LOGGER.exception('Error sending to Logentries: %s', error)

    hass.bus.listen(EVENT_STATE_CHANGED, logentries_event_listener)

    return True
