"""
A component which allows you to send data to StatsD.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/statsd/
"""
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_HOST, CONF_PORT, CONF_PREFIX, EVENT_STATE_CHANGED)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import state as state_helper

REQUIREMENTS = ['statsd==3.2.1']

_LOGGER = logging.getLogger(__name__)

CONF_ATTR = 'log_attributes'
CONF_RATE = 'rate'

DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 8125
DEFAULT_PREFIX = 'hass'
DEFAULT_RATE = 1
DOMAIN = 'statsd'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_ATTR, default=False): cv.boolean,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_PREFIX, default=DEFAULT_PREFIX): cv.string,
        vol.Optional(CONF_RATE, default=DEFAULT_RATE):
            vol.All(vol.Coerce(int), vol.Range(min=1)),
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Setup the StatsD component."""
    import statsd

    conf = config[DOMAIN]
    host = conf.get(CONF_HOST)
    port = conf.get(CONF_PORT)
    sample_rate = conf.get(CONF_RATE)
    prefix = conf.get(CONF_PREFIX)
    show_attribute_flag = conf.get(CONF_ATTR)

    statsd_client = statsd.StatsClient(host=host, port=port, prefix=prefix)

    def statsd_event_listener(event):
        """Listen for new messages on the bus and sends them to StatsD."""
        state = event.data.get('new_state')

        if state is None:
            return

        try:
            _state = state_helper.state_as_number(state)
        except ValueError:
            return

        states = dict(state.attributes)

        _LOGGER.debug('Sending %s.%s', state.entity_id, _state)

        if show_attribute_flag is True:
            statsd_client.gauge(
                "%s.state" % state.entity_id,
                _state,
                sample_rate
            )

            # Send attribute values
            for key, value in states.items():
                if isinstance(value, (float, int)):
                    stat = "%s.%s" % (state.entity_id, key.replace(' ', '_'))
                    statsd_client.gauge(stat, value, sample_rate)

        else:
            statsd_client.gauge(state.entity_id, _state, sample_rate)

        # Increment the count
        statsd_client.incr(state.entity_id, rate=sample_rate)

    hass.bus.listen(EVENT_STATE_CHANGED, statsd_event_listener)

    return True
