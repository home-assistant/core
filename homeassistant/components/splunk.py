"""
homeassistant.components.splunk
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Splunk component which allows you to send data to an Splunk instance
utilizing the HTTP Event Collector.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/splunk/
"""
import json
import logging

import requests

import homeassistant.util as util
from homeassistant.helpers import validate_config
from homeassistant.const import (EVENT_STATE_CHANGED, STATE_ON, STATE_OFF,
                                 STATE_UNLOCKED, STATE_LOCKED, STATE_UNKNOWN)
from homeassistant.components.sun import (STATE_ABOVE_HORIZON,
                                          STATE_BELOW_HORIZON)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "splunk"
DEPENDENCIES = []

DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 8088
DEFAULT_SSL = False

CONF_HOST = 'host'
CONF_PORT = 'port'
CONF_TOKEN = 'token'
CONF_SSL = 'SSL'


def setup(hass, config):
    """ Setup the Splunk component. """

    if not validate_config(config, {DOMAIN: ['token']}, _LOGGER):
        _LOGGER.error("You must include the token for your HTTP "
                      "Event Collector input in Splunk.")
        return False

    conf = config[DOMAIN]

    host = conf[CONF_HOST]
    port = util.convert(conf.get(CONF_PORT), int, DEFAULT_PORT)
    token = util.convert(conf.get(CONF_TOKEN), str)
    use_ssl = util.convert(conf.get(CONF_SSL), bool, DEFAULT_SSL)
    uri_scheme = "https://" if use_ssl else "http://"
    event_collector = "{}{}:{}/services/collector/event".format(uri_scheme,
                                                                host, port)
    headers = {'Authorization': 'Splunk ' + token}

    def splunk_event_listener(event):
        """ Listen for new messages on the bus and sends them to Splunk. """

        state = event.data.get('new_state')

        if state is None:
            return

        if state.state in (STATE_ON, STATE_LOCKED, STATE_ABOVE_HORIZON):
            _state = 1
        elif state.state in (STATE_OFF, STATE_UNLOCKED, STATE_UNKNOWN,
                             STATE_BELOW_HORIZON):
            _state = 0
        else:
            _state = state.state
            try:
                _state = float(_state)
            except ValueError:
                pass

        json_body = [
            {
                'domain': state.domain,
                'entity_id': state.object_id,
                'attributes': state.attributes,
                'time': str(event.time_fired),
                'value': _state,
            }
        ]

        try:
            payload = {"host": event_collector,
                       "event": json_body}
            requests.post(event_collector, data=json.dumps(payload),
                          headers=headers)
        except requests.exceptions.RequestException as error:
            _LOGGER.exception('Error saving event to Splunk: %s', error)

    hass.bus.listen(EVENT_STATE_CHANGED, splunk_event_listener)

    return True
