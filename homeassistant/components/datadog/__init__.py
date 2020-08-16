"""Support for sending data to Datadog."""
import logging

from datadog import initialize, statsd
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_PREFIX,
    EVENT_LOGBOOK_ENTRY,
    EVENT_STATE_CHANGED,
    STATE_UNKNOWN,
)
from homeassistant.helpers import state as state_helper
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_RATE = "rate"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8125
DEFAULT_PREFIX = "hass"
DEFAULT_RATE = 1
DOMAIN = "datadog"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_PREFIX, default=DEFAULT_PREFIX): cv.string,
                vol.Optional(CONF_RATE, default=DEFAULT_RATE): vol.All(
                    vol.Coerce(int), vol.Range(min=1)
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up the Datadog component."""

    conf = config[DOMAIN]
    host = conf[CONF_HOST]
    port = conf[CONF_PORT]
    sample_rate = conf[CONF_RATE]
    prefix = conf[CONF_PREFIX]

    initialize(statsd_host=host, statsd_port=port)

    def logbook_entry_listener(event):
        """Listen for logbook entries and send them as events."""
        name = event.data.get("name")
        message = event.data.get("message")

        statsd.event(
            title="Home Assistant",
            text=f"%%% \n **{name}** {message} \n %%%",
            tags=[
                f"entity:{event.data.get('entity_id')}",
                f"domain:{event.data.get('domain')}",
            ],
        )

        _LOGGER.debug("Sent event %s", event.data.get("entity_id"))

    def state_changed_listener(event):
        """Listen for new messages on the bus and sends them to Datadog."""
        state = event.data.get("new_state")

        if state is None or state.state == STATE_UNKNOWN:
            return

        states = dict(state.attributes)
        metric = f"{prefix}.{state.domain}"
        tags = [f"entity:{state.entity_id}"]

        for key, value in states.items():
            if isinstance(value, (float, int)):
                attribute = f"{metric}.{key.replace(' ', '_')}"
                value = int(value) if isinstance(value, bool) else value
                statsd.gauge(attribute, value, sample_rate=sample_rate, tags=tags)

                _LOGGER.debug("Sent metric %s: %s (tags: %s)", attribute, value, tags)

        try:
            value = state_helper.state_as_number(state)
        except ValueError:
            _LOGGER.debug("Error sending %s: %s (tags: %s)", metric, state.state, tags)
            return

        statsd.gauge(metric, value, sample_rate=sample_rate, tags=tags)

        _LOGGER.debug("Sent metric %s: %s (tags: %s)", metric, value, tags)

    hass.bus.listen(EVENT_LOGBOOK_ENTRY, logbook_entry_listener)
    hass.bus.listen(EVENT_STATE_CHANGED, state_changed_listener)

    return True
