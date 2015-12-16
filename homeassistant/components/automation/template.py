"""
homeassistant.components.automation.template
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Offers template automation rules.

For more details about this automation rule, please refer to the documentation
at https://home-assistant.io/components/automation/#template-trigger
"""
import logging

from homeassistant.const import CONF_VALUE_TEMPLATE
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.event import track_state_change
from homeassistant.util import template

_LOGGER = logging.getLogger(__name__)


def trigger(hass, config, action):
    """ Listen for state changes based on `config`. """
    value_template = config.get(CONF_VALUE_TEMPLATE)

    if value_template is None:
        _LOGGER.error("Missing configuration key %s", CONF_VALUE_TEMPLATE)
        return False

    # Get all entity ids
    all_entity_ids = hass.states.entity_ids()

    # pylint: disable=unused-argument
    def state_automation_listener(entity, from_s, to_s):
        """ Listens for state changes and calls action. """

        # Check to see if template returns true
        if _check_template(hass, value_template):
            action()

    track_state_change(hass, all_entity_ids, state_automation_listener)

    return True


def if_action(hass, config):
    """ Wraps action method with state based condition. """

    value_template = config.get(CONF_VALUE_TEMPLATE)

    if value_template is None:
        _LOGGER.error("Missing configuration key %s", CONF_VALUE_TEMPLATE)
        return False

    return lambda: _check_template(hass, value_template)


def _check_template(hass, value_template):
    """ Checks if result of template is true """
    try:
        value = template.render(hass, value_template, {})
    except TemplateError:
        _LOGGER.exception('Error parsing template')
        return False

    return value.lower() == 'true'
