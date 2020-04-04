"""Support to send data to an Splunk instance."""
import json
import logging

from aiohttp.hdrs import AUTHORIZATION
import requests
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SSL,
    CONF_TOKEN,
    CONF_VERIFY_SSL,
    EVENT_STATE_CHANGED,
)
from homeassistant.helpers import state as state_helper
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import FILTER_SCHEMA
from homeassistant.helpers.json import JSONEncoder

_LOGGER = logging.getLogger(__name__)

CONF_FILTER = "filter"
DOMAIN = "splunk"

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8088
DEFAULT_SSL = False
DEFAULT_NAME = "HASS"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_TOKEN): cv.string,
                vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_SSL, default=False): cv.boolean,
                vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(CONF_FILTER, default={}): FILTER_SCHEMA,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def post_request(event_collector, body, headers, verify_ssl):
    """Post request to Splunk."""
    try:
        payload = {"host": event_collector, "event": body}
        requests.post(
            event_collector,
            data=json.dumps(payload, cls=JSONEncoder),
            headers=headers,
            timeout=10,
            verify=verify_ssl,
        )

    except requests.exceptions.RequestException as error:
        _LOGGER.exception("Error saving event to Splunk: %s", error)


def setup(hass, config):
    """Set up the Splunk component."""
    conf = config[DOMAIN]
    host = conf.get(CONF_HOST)
    port = conf.get(CONF_PORT)
    token = conf.get(CONF_TOKEN)
    use_ssl = conf.get(CONF_SSL)
    verify_ssl = conf.get(CONF_VERIFY_SSL)
    name = conf.get(CONF_NAME)
    entity_filter = conf[CONF_FILTER]

    if use_ssl:
        uri_scheme = "https://"
    else:
        uri_scheme = "http://"

    event_collector = f"{uri_scheme}{host}:{port}/services/collector/event"
    headers = {AUTHORIZATION: f"Splunk {token}"}

    def splunk_event_listener(event):
        """Listen for new messages on the bus and sends them to Splunk."""
        state = event.data.get("new_state")

        if state is None or not entity_filter(state.entity_id):
            return

        try:
            _state = state_helper.state_as_number(state)
        except ValueError:
            _state = state.state

        json_body = [
            {
                "domain": state.domain,
                "entity_id": state.object_id,
                "attributes": dict(state.attributes),
                "time": str(event.time_fired),
                "value": _state,
                "host": name,
            }
        ]

        post_request(event_collector, json_body, headers, verify_ssl)

    hass.bus.listen(EVENT_STATE_CHANGED, splunk_event_listener)

    return True
