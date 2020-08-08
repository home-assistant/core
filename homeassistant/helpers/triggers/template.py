"""Offer template automation rules."""
import logging

import voluptuous as vol

from homeassistant import exceptions
from homeassistant.const import CONF_FOR, CONF_PLATFORM, CONF_VALUE_TEMPLATE
from homeassistant.core import callback
from homeassistant.helpers import condition, config_validation as cv, template
from homeassistant.helpers.event import async_track_same_state, async_track_template

# mypy: allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)

TRIGGER_SCHEMA = IF_ACTION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM): "template",
        vol.Required(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_FOR): cv.positive_time_period_template,
    }
)


async def async_attach_trigger(
    hass, config, action, automation_info, *, platform_type="numeric_state"
):
    """Listen for state changes based on configuration."""
    value_template = config.get(CONF_VALUE_TEMPLATE)
    value_template.hass = hass
    time_delta = config.get(CONF_FOR)
    template.attach(hass, time_delta)
    unsub_track_same = None

    @callback
    def template_listener(entity_id, from_s, to_s):
        """Listen for state changes and calls action."""
        nonlocal unsub_track_same

        @callback
        def call_action():
            """Call action with right context."""
            hass.async_run_job(
                action(
                    {
                        "trigger": {
                            "platform": "template",
                            "entity_id": entity_id,
                            "from_state": from_s,
                            "to_state": to_s,
                            "for": time_delta if not time_delta else period,
                        }
                    },
                    context=(to_s.context if to_s else None),
                )
            )

        if not time_delta:
            call_action()
            return

        variables = {
            "trigger": {
                "platform": platform_type,
                "entity_id": entity_id,
                "from_state": from_s,
                "to_state": to_s,
            }
        }

        try:
            period = cv.positive_time_period(
                template.render_complex(time_delta, variables)
            )
        except (exceptions.TemplateError, vol.Invalid) as ex:
            _LOGGER.error(
                "Error rendering '%s' for template: %s", automation_info["name"], ex
            )
            return

        unsub_track_same = async_track_same_state(
            hass,
            period,
            call_action,
            lambda _, _2, _3: condition.async_template(hass, value_template),
            value_template.extract_entities(),
        )

    unsub = async_track_template(hass, value_template, template_listener)

    @callback
    def async_remove():
        """Remove state listeners async."""
        unsub()
        if unsub_track_same:
            # pylint: disable=not-callable
            unsub_track_same()

    return async_remove
