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

REQUIREMENTS = ['python-statsd==1.7.2']

CONF_HOST = 'host'
CONF_PORT = 'port'
CONF_PREFIX = 'prefix'
CONF_RATE = 'rate'


def setup(hass, config):
    """Setup the StatsD component."""
    from statsd.compat import NUM_TYPES
    import statsd

    conf = config[DOMAIN]

    host = conf[CONF_HOST]
    port = util.convert(conf.get(CONF_PORT), int, DEFAULT_PORT)
    sample_rate = util.convert(conf.get(CONF_RATE), int, DEFAULT_RATE)
    prefix = util.convert(conf.get(CONF_PREFIX), str, DEFAULT_PREFIX)

    statsd_connection = statsd.Connection(
        host=host,
        port=port,
        sample_rate=sample_rate,
        disabled=False
    )

    meter = statsd.Gauge(prefix, statsd_connection)

    def statsd_event_listener(event):
        """Listen for new messages on the bus and sends them to StatsD."""
        state = event.data.get('new_state')

        if state is None:
            return

        try:
            _state = state_helper.state_as_number(state)
        except ValueError:
            return

        if not isinstance(_state, NUM_TYPES):
            return

        _LOGGER.debug('Sending %s.%s', state.entity_id, _state)
        meter.send(state.entity_id, _state)

    hass.bus.listen(EVENT_STATE_CHANGED, statsd_event_listener)

    return True
