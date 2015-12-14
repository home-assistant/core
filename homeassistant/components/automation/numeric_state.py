"""
homeassistant.components.automation.numeric_state
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Offers numeric state listening automation rules.

For more details about this automation rule, please refer to the documentation
at https://home-assistant.io/components/automation/#numeric-state-trigger
"""
import logging

from homeassistant.const import CONF_VALUE_TEMPLATE
from homeassistant.helpers.event import track_state_change
from homeassistant.util import template


CONF_ENTITY_ID = "entity_id"
CONF_BELOW = "below"
CONF_ABOVE = "above"

_LOGGER = logging.getLogger(__name__)


def trigger(hass, config, action):
    """ Listen for state changes based on `config`. """
    entity_id = config.get(CONF_ENTITY_ID)

    if entity_id is None:
        _LOGGER.error("Missing configuration key %s", CONF_ENTITY_ID)
        return False

    below = config.get(CONF_BELOW)
    above = config.get(CONF_ABOVE)
    value_template = config.get(CONF_VALUE_TEMPLATE)

    if below is None and above is None:
        _LOGGER.error("Missing configuration key."
                      " One of %s or %s is required",
                      CONF_BELOW, CONF_ABOVE)
        return False

    if value_template is not None:
        renderer = lambda value: template.render(hass, value_template, value)
    else:
        renderer = None

    # pylint: disable=unused-argument
    def state_automation_listener(entity, from_s, to_s):
        """ Listens for state changes and calls action. """

        # Fire action if we go from outside range into range
        if _in_range(to_s, above, below, renderer) and \
           (from_s is None or not _in_range(from_s, above, below, renderer)):
            action()

    track_state_change(
        hass, entity_id, state_automation_listener)

    return True


def if_action(hass, config):
    """ Wraps action method with state based condition. """

    entity_id = config.get(CONF_ENTITY_ID)

    if entity_id is None:
        _LOGGER.error("Missing configuration key %s", CONF_ENTITY_ID)
        return None

    below = config.get(CONF_BELOW)
    above = config.get(CONF_ABOVE)
    value_template = config.get(CONF_VALUE_TEMPLATE)

    if below is None and above is None:
        _LOGGER.error("Missing configuration key."
                      " One of %s or %s is required",
                      CONF_BELOW, CONF_ABOVE)
        return None

    if value_template is not None:
        renderer = lambda value: template.render(hass, value_template, value)
    else:
        renderer = None

    def if_numeric_state():
        """ Test numeric state condition. """
        state = hass.states.get(entity_id)
        return state is not None and _in_range(state, above, below,
                                               renderer)

    return if_numeric_state


def _in_range(state, range_start, range_end, renderer):
    """ Checks if value is inside the range """

    if renderer is not None:
        value = renderer({'value': state})
    else:
        # If no renderer is provided, just assume they want the state
        value = state.state

    try:
        value = float(value)
    except ValueError:
        _LOGGER.warning("Missing value in numeric check")
        return False

    if range_start is not None and range_end is not None:
        return float(range_start) <= value < float(range_end)
    elif range_end is not None:
        return value < float(range_end)
    else:
        return float(range_start) <= value
