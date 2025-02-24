"""Support for sending data to StatsD."""

import logging

import statsd
import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_PREFIX, EVENT_STATE_CHANGED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, state as state_helper
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

CONF_ATTR = "log_attributes"
CONF_RATE = "rate"
CONF_VALUE_MAP = "value_mapping"

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8125
DEFAULT_PREFIX = "hass"
DEFAULT_RATE = 1
DOMAIN = "statsd"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
                vol.Optional(CONF_ATTR, default=False): cv.boolean,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_PREFIX, default=DEFAULT_PREFIX): cv.string,
                vol.Optional(CONF_RATE, default=DEFAULT_RATE): vol.All(
                    vol.Coerce(int), vol.Range(min=1)
                ),
                vol.Optional(CONF_VALUE_MAP): dict,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the StatsD component."""

    conf = config[DOMAIN]
    host = conf.get(CONF_HOST)
    port = conf.get(CONF_PORT)
    sample_rate = conf.get(CONF_RATE)
    prefix = conf.get(CONF_PREFIX)
    value_mapping = conf.get(CONF_VALUE_MAP)
    show_attribute_flag = conf.get(CONF_ATTR)

    statsd_client = statsd.StatsClient(host=host, port=port, prefix=prefix)

    def statsd_event_listener(event):
        """Listen for new messages on the bus and sends them to StatsD."""
        if (state := event.data.get("new_state")) is None:
            return

        try:
            if value_mapping and state.state in value_mapping:
                _state = float(value_mapping[state.state])
            else:
                _state = state_helper.state_as_number(state)
        except ValueError:
            # Set the state to none and continue for any numeric attributes.
            _state = None

        states = dict(state.attributes)

        _LOGGER.debug("Sending %s", state.entity_id)

        if show_attribute_flag is True:
            if isinstance(_state, (float, int)):
                statsd_client.gauge(f"{state.entity_id}.state", _state, sample_rate)

            # Send attribute values
            for key, value in states.items():
                if isinstance(value, (float, int)):
                    stat = f"{state.entity_id}.{key.replace(' ', '_')}"
                    statsd_client.gauge(stat, value, sample_rate)

        elif isinstance(_state, (float, int)):
            statsd_client.gauge(state.entity_id, _state, sample_rate)

        # Increment the count
        statsd_client.incr(state.entity_id, rate=sample_rate)

    hass.bus.listen(EVENT_STATE_CHANGED, statsd_event_listener)

    return True
