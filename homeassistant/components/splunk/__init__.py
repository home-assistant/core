"""Support to send data to an Splunk instance."""
import logging

from splunk_http_event_collector import http_event_collector
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

_LOGGER = logging.getLogger(__name__)

CONF_FILTER = "filter"
FORMAT_JSON = "json"
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

    event_collector = http_event_collector(
        token, host, FORMAT_JSON, name, port, use_ssl
    )
    event_collector.SSL_verify = verify_ssl

    if not event_collector.check_connectivity():
        _LOGGER.exception("Error while trying to connect to Splunk")

    def splunk_event_listener(event):
        """Listen for new messages on the bus and sends them to Splunk."""
        state = event.data.get("new_state")

        if state is None or not entity_filter(state.entity_id):
            return

        try:
            _state = state_helper.state_as_number(state)
        except ValueError:
            _state = state.state

        payload = {
            "time": event.time_fired.timestamp(),
            "host": name,
            "event": {
                "domain": state.domain,
                "entity_id": state.object_id,
                "attributes": dict(state.attributes),
                "value": _state,
            },
        }
        event_collector.batchEvent(payload)

    def splunk_event_flush(event):
        event_collector.flushBatch()

    hass.bus.listen(EVENT_STATE_CHANGED, splunk_event_listener)
    hass.bus.listen(EVENT_TIME_CHANGED, splunk_event_flush)
    hass.bus.listen(EVENT_HOMEASSISTANT_STOP, splunk_event_flush)

    return True
