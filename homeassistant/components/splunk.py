"""
Support to send data to an Splunk instance.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/splunk/
"""
import json
import logging

import requests
import voluptuous as vol

from homeassistant.const import (
    CONF_NAME, CONF_HOST, CONF_PORT, CONF_SSL, CONF_TOKEN, EVENT_STATE_CHANGED)
from homeassistant.helpers import state as state_helper
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'splunk'

DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 8088
DEFAULT_SSL = False
DEFAULT_NAME = 'HASS'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_TOKEN): cv.string,
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SSL, default=False): cv.boolean,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Splunk component."""
    conf = config[DOMAIN]
    host = conf.get(CONF_HOST)
    port = conf.get(CONF_PORT)
    token = conf.get(CONF_TOKEN)
    use_ssl = conf.get(CONF_SSL)
    name = conf.get(CONF_NAME)

    if use_ssl:
        uri_scheme = 'https://'
    else:
        uri_scheme = 'http://'

    event_collector = '{}{}:{}/services/collector/event'.format(
        uri_scheme, host, port)
    headers = {'Authorization': 'Splunk {}'.format(token)}

    def splunk_event_listener(event):
        """Listen for new messages on the bus and sends them to Splunk."""
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
                'host': name,
            }
        ]

        try:
            payload = {
                "host": event_collector,
                "event": json_body,
            }
            requests.post(event_collector, data=json.dumps(payload),
                          headers=headers, timeout=10)
        except requests.exceptions.RequestException as error:
            _LOGGER.exception("Error saving event to Splunk: %s", error)

    hass.bus.listen(EVENT_STATE_CHANGED, splunk_event_listener)

    return True
