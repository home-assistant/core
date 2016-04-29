"""
Support for sending data to Logentries webhook endpoint.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/logentries/
"""
import json
import logging

import requests

import homeassistant.util as util
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.helpers import state as state_helper
from homeassistant.helpers import validate_config

_LOGGER = logging.getLogger(__name__)

DOMAIN = "logentries"
DEPENDENCIES = []

DEFAULT_HOST = 'webhook.logentries.com'
DEFAULT_SSL = False

CONF_TOKEN = 'token'
CONF_SSL = 'SSL'


def setup(hass, config):
    """Setup the Logentries component."""
    if not validate_config(config, {DOMAIN: ['token']}, _LOGGER):
        _LOGGER.error("Logentries token not present")
        return False

    conf = config[DOMAIN]

    token = util.convert(conf.get(CONF_TOKEN), str)
    use_ssl = util.convert(conf.get(CONF_SSL), bool, DEFAULT_SSL)
    if use_ssl:
        uri_scheme = "https://"
    else:
        uri_scheme = "http://"
    le_wh = uri_scheme + DEFAULT_HOST + "/" + token + "/"

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
            requests.post(le_wh, data=json.dumps(payload))
        except requests.exceptions.RequestException as error:
            _LOGGER.exception('Error sending to Logentries: %s', error)

    hass.bus.listen(EVENT_STATE_CHANGED, logentries_event_listener)

    return True
