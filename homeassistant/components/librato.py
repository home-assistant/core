"""
homeassistant.components.librato
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Send metrics to Librato Metrics

"""
import logging
from homeassistant.helpers import validate_config
from homeassistant.const import (EVENT_STATE_CHANGED, STATE_ON, STATE_OFF,
                                 STATE_UNLOCKED, STATE_LOCKED, STATE_UNKNOWN)
from homeassistant.components.sun import (STATE_ABOVE_HORIZON,
                                          STATE_BELOW_HORIZON)

_LOGGER = logging.getLogger(__name__)

logging.getLogger("librato").setLevel(logging.WARNING)

DOMAIN = "librato"
DEPENDENCIES = []

REQUIREMENTS = ['librato-metrics==0.8.5']

CONF_USER = 'user'
CONF_TOKEN = 'token'
CONF_NAMESPACE = 'namespace'


# pylint: disable=too-many-branches
def setup(hass, config):
    """ Setup the Librato component. """

    import librato

    if not validate_config(config, {DOMAIN: [CONF_USER, CONF_TOKEN]}, _LOGGER):
        return False

    conf = config[DOMAIN]
    user = conf[CONF_USER]
    token = conf[CONF_TOKEN]
    namespace = conf.get(CONF_NAMESPACE, '')
    if namespace != '':
        namespace = namespace + '.'

    metrics = librato.connect(
        user,
        token,
        sanitizer=librato.sanitize_metric_name)

    def metrics_listener(event):
        """ Listen for new messages on the bus and send metrics to Librato. """
        state = event.data.get('new_state')

        with metrics.new_queue() as metrics_queue:

            # Attempt to parse the state and try to transform it into a float.
            _state = None
            if state.state in (STATE_ON, STATE_LOCKED, STATE_ABOVE_HORIZON):
                _state = 1
            elif state.state in (STATE_OFF, STATE_UNLOCKED, STATE_UNKNOWN,
                                 STATE_BELOW_HORIZON):
                _state = 0
            else:
                _state = state.state
                if _state and isinstance(_state, str):
                    try:
                        _state = float(_state)
                    except ValueError:
                        _state = None

                if _state and isinstance(_state, int):
                    _state = float(_state)

            if _state is not None:
                metrics_queue.add(
                    (namespace + 'states.' + state.entity_id),
                    _state)

            # Now inspect the attributes and submit anything that looks like a
            # float
            attributes = dict(state.attributes)
            ignored_attributes = [
                'hidden',
                'can_cancel',
                'media_title',
                'supported_media_commands',
                'node_id',
                'auto'
            ]
            for key in attributes:
                if key in ignored_attributes:
                    continue
                try:
                    value = float(attributes[key])
                    metrics_queue.add(
                        (namespace + 'states.' + state.entity_id + '.' + key),
                        value)
                except (TypeError, ValueError):
                    pass

    hass.bus.listen(EVENT_STATE_CHANGED, metrics_listener)

    return True
