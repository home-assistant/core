"""
Offer numeric state listening automation rules.

For more details about this automation rule, please refer to the documentation
at https://home-assistant.io/components/automation/#numeric-state-trigger
"""
import logging
from functools import partial

from homeassistant.const import CONF_VALUE_TEMPLATE
from homeassistant.helpers.event import track_state_change
from homeassistant.helpers import template

CONF_ENTITY_ID = "entity_id"
CONF_BELOW = "below"
CONF_ABOVE = "above"

_LOGGER = logging.getLogger(__name__)


def _renderer(hass, value_template, state):
    """Render the state value."""
    if value_template is None:
        return state.state

    return template.render(hass, value_template, {'state': state})


def trigger(hass, config, action):
    """Listen for state changes based on configuration."""
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

    renderer = partial(_renderer, hass, value_template)

    # pylint: disable=unused-argument
    def state_automation_listener(entity, from_s, to_s):
        """Listen for state changes and calls action."""
        # Fire action if we go from outside range into range
        if _in_range(above, below, renderer(to_s)) and \
           (from_s is None or not _in_range(above, below, renderer(from_s))):
            action()

    track_state_change(
        hass, entity_id, state_automation_listener)

    return True


def if_action(hass, config):
    """Wrap action method with state based condition."""
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

    renderer = partial(_renderer, hass, value_template)

    def if_numeric_state():
        """Test numeric state condition."""
        state = hass.states.get(entity_id)
        return state is not None and _in_range(above, below, renderer(state))

    return if_numeric_state


def _in_range(range_start, range_end, value):
    """Check if value is inside the range."""
    try:
        value = float(value)
    except ValueError:
        _LOGGER.warning("Value returned from template is not a number: %s",
                        value)
        return False

    if range_start is not None and range_end is not None:
        return float(range_start) <= value < float(range_end)
    elif range_end is not None:
        return value < float(range_end)
    else:
        return float(range_start) <= value
