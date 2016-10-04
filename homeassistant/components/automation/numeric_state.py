"""
Offer numeric state listening automation rules.

For more details about this automation rule, please refer to the documentation
at https://home-assistant.io/components/automation/#numeric-state-trigger
"""
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import (
    CONF_VALUE_TEMPLATE, CONF_PLATFORM, CONF_ENTITY_ID,
    CONF_BELOW, CONF_ABOVE)
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers import condition, config_validation as cv

TRIGGER_SCHEMA = vol.All(vol.Schema({
    vol.Required(CONF_PLATFORM): 'numeric_state',
    vol.Required(CONF_ENTITY_ID): cv.entity_ids,
    CONF_BELOW: vol.Coerce(float),
    CONF_ABOVE: vol.Coerce(float),
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
}), cv.has_at_least_one_key(CONF_BELOW, CONF_ABOVE))

_LOGGER = logging.getLogger(__name__)


def async_trigger(hass, config, action):
    """Listen for state changes based on configuration."""
    entity_id = config.get(CONF_ENTITY_ID)
    below = config.get(CONF_BELOW)
    above = config.get(CONF_ABOVE)
    value_template = config.get(CONF_VALUE_TEMPLATE)
    if value_template is not None:
        value_template.hass = hass

    @callback
    def state_automation_listener(entity, from_s, to_s):
        """Listen for state changes and calls action."""
        if to_s is None:
            return

        variables = {
            'trigger': {
                'platform': 'numeric_state',
                'entity_id': entity,
                'below': below,
                'above': above,
            }
        }

        # If new one doesn't match, nothing to do
        if not condition.async_numeric_state(
                hass, to_s, below, above, value_template, variables):
            return

        # Only match if old didn't exist or existed but didn't match
        # Written as: skip if old one did exist and matched
        if from_s is not None and condition.async_numeric_state(
                hass, from_s, below, above, value_template, variables):
            return

        variables['trigger']['from_state'] = from_s
        variables['trigger']['to_state'] = to_s

        hass.async_run_job(action, variables)

    return async_track_state_change(hass, entity_id, state_automation_listener)
