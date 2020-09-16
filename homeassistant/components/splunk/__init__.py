"""Support to send data to an Splunk instance."""
import json
import logging
import time

from requests.exceptions import ConnectionError, HTTPError, Timeout, TooManyRedirects
from splunk_data_sender import SplunkSender
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SSL,
    CONF_TOKEN,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_STATE_CHANGED,
    EVENT_TIME_CHANGED,
)
from homeassistant.helpers import state as state_helper
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import FILTER_SCHEMA
from homeassistant.helpers.json import JSONEncoder

_LOGGER = logging.getLogger(__name__)

DOMAIN = "splunk"
CONF_FILTER = "filter"
SPLUNK_ENDPOINT = "collector/event"

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


def setup(hass, config):
    """Set up the Splunk component."""
    conf = config[DOMAIN]
    host = conf.get(CONF_HOST)
    port = conf.get(CONF_PORT)
    token = conf.get(CONF_TOKEN)
    use_ssl = conf[CONF_SSL]
    verify_ssl = conf.get(CONF_VERIFY_SSL)
    name = conf.get(CONF_NAME)
    entity_filter = conf[CONF_FILTER]

    if verify_ssl and not use_ssl:
        _LOGGER.error("You cannot use verify_ssl without ssl")
        return False

    event_collector = SplunkSender(
        host=host,
        port=port,
        token=token,
        hostname=name,
        protocol=["http", "https"][use_ssl],
        verify=verify_ssl,
        api_url=SPLUNK_ENDPOINT,
    )

    batch = []

    def queue(payload):
        batch.append(json.dumps(payload, cls=JSONEncoder))

    payload = {
        "time": time.time(),
        "host": name,
        "event": {
            "domain": DOMAIN,
            "meta": "Home Assistant has started",
            "value": 1,
        },
    }

    try:
        event_collector._send_to_splunk("send-event", json.dumps(payload))
    except HTTPError as e:
        if e.response.status_code in (401, 403):
            _LOGGER.error("Invalid or disabled token")
            return False
        else:
            _LOGGER.warn(e)
    except (Timeout, ConnectionError, TooManyRedirects) as e:
        _LOGGER.warn(e)

    def splunk_event_listener(event):
        """Listen for new messages on the bus and sends them to Splunk."""

        nonlocal batch
        state = event.data.get("new_state")

        if state is None or not entity_filter(state.entity_id):
            return

        try:
            _state = state_helper.state_as_number(state)
        except ValueError:
            _state = state.state

        queue(
            {
                "time": event.time_fired.timestamp(),
                "host": name,
                "event": {
                    "domain": state.domain,
                    "entity_id": state.object_id,
                    "attributes": dict(state.attributes),
                    "value": _state,
                },
            }
        )
        return True

    def splunk_send(event=None):
        """Send batched messages to Splunk every second."""
        nonlocal batch
        if len(batch):
            events = batch
            batch = []
            try:
                event_collector._send_to_splunk("send-event", "".join(events))
            except (HTTPError, Timeout, ConnectionError, TooManyRedirects) as e:
                _LOGGER.warn(e)

    def splunk_stop(event):
        queue(
            {
                "time": event.time_fired.timestamp(),
                "host": name,
                "event": {
                    "domain": DOMAIN,
                    "meta": "Home Assistant is stopping",
                    "value": 0,
                },
            }
        )
        splunk_send()

    hass.bus.listen(EVENT_STATE_CHANGED, splunk_event_listener)
    hass.bus.listen(EVENT_TIME_CHANGED, splunk_send)
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, splunk_stop)

    return True
