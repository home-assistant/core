"""
Offer template automation rules.

For more details about this automation rule, please refer to the documentation
at https://home-assistant.io/components/automation/#template-trigger
"""
import logging

from homeassistant.const import CONF_VALUE_TEMPLATE, EVENT_STATE_CHANGED
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import template

_LOGGER = logging.getLogger(__name__)


def trigger(hass, config, action):
    """Listen for state changes based on configuration."""
    value_template = config.get(CONF_VALUE_TEMPLATE)

    if value_template is None:
        _LOGGER.error("Missing configuration key %s", CONF_VALUE_TEMPLATE)
        return False

    # Local variable to keep track of if the action has already been triggered
    already_triggered = False

    def event_listener(event):
        """Listen for state changes and calls action."""
        nonlocal already_triggered
        template_result = _check_template(hass, value_template)

        # Check to see if template returns true
        if template_result and not already_triggered:
            already_triggered = True
            action()
        elif not template_result:
            already_triggered = False

    hass.bus.listen(EVENT_STATE_CHANGED, event_listener)
    return True


def if_action(hass, config):
    """Wrap action method with state based condition."""
    value_template = config.get(CONF_VALUE_TEMPLATE)

    if value_template is None:
        _LOGGER.error("Missing configuration key %s", CONF_VALUE_TEMPLATE)
        return False

    return lambda: _check_template(hass, value_template)


def _check_template(hass, value_template):
    """Check if result of template is true."""
    try:
        value = template.render(hass, value_template, {})
    except TemplateError:
        _LOGGER.exception('Error parsing template')
        return False

    return value.lower() == 'true'
