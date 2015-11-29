"""
homeassistant.components.automation.numeric_state
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Offers numeric state listening automation rules.

For more details about this automation rule, please refer to the documentation
at https://home-assistant.io/components/automation/#numeric-state-trigger
"""
import logging

from homeassistant.helpers.event import track_state_change


CONF_ENTITY_ID = "entity_id"
CONF_BELOW = "below"
CONF_ABOVE = "above"
CONF_ATTRIBUTE = "attribute"

_LOGGER = logging.getLogger(__name__)


def trigger(hass, config, action):
    """ Listen for state changes based on `config`. """
    entity_id = config.get(CONF_ENTITY_ID)

    if entity_id is None:
        _LOGGER.error("Missing configuration key %s", CONF_ENTITY_ID)
        return False

    below = config.get(CONF_BELOW)
    above = config.get(CONF_ABOVE)
    attribute = config.get(CONF_ATTRIBUTE)

    if below is None and above is None:
        _LOGGER.error("Missing configuration key."
                      " One of %s or %s is required",
                      CONF_BELOW, CONF_ABOVE)
        return False

    # pylint: disable=unused-argument
    def state_automation_listener(entity, from_s, to_s):
        """ Listens for state changes and calls action. """

        # Fire action if we go from outside range into range
        if _in_range(to_s, above, below, attribute) and \
           (from_s is None or not _in_range(from_s, above, below, attribute)):
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
    attribute = config.get(CONF_ATTRIBUTE)

    if below is None and above is None:
        _LOGGER.error("Missing configuration key."
                      " One of %s or %s is required",
                      CONF_BELOW, CONF_ABOVE)
        return None

    def if_numeric_state():
        """ Test numeric state condition. """
        state = hass.states.get(entity_id)
        return state is not None and _in_range(state, above, below, attribute)

    return if_numeric_state


def _in_range(state, range_start, range_end, attribute):
    """ Checks if value is inside the range """
    value = (state.state if attribute is None
             else state.attributes.get(attribute))
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
