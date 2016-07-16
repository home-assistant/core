"""
A component which allows you to send data to StatsD.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/statsd/
"""
import logging

import homeassistant.util as util
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.helpers import state as state_helper

_LOGGER = logging.getLogger(__name__)

DOMAIN = "statsd"
DEPENDENCIES = []

DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 8125
DEFAULT_PREFIX = 'hass'
DEFAULT_RATE = 1

REQUIREMENTS = ['statsd==3.2.1']

CONF_HOST = 'host'
CONF_PORT = 'port'
CONF_PREFIX = 'prefix'
CONF_RATE = 'rate'
CONF_ATTR = 'log_attributes'


def setup(hass, config):
    """Setup the StatsD component."""
    import statsd

    conf = config[DOMAIN]

    host = conf[CONF_HOST]
    port = util.convert(conf.get(CONF_PORT), int, DEFAULT_PORT)
    sample_rate = util.convert(conf.get(CONF_RATE), int, DEFAULT_RATE)
    prefix = util.convert(conf.get(CONF_PREFIX), str, DEFAULT_PREFIX)
    show_attribute_flag = conf.get(CONF_ATTR, False)

    statsd_client = statsd.StatsClient(
        host=host,
        port=port,
        prefix=prefix
    )

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
