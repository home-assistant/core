"""Offer template automation rules."""
import logging

import voluptuous as vol

from homeassistant import exceptions
from homeassistant.const import CONF_FOR, CONF_PLATFORM, CONF_VALUE_TEMPLATE
from homeassistant.core import HassJob, callback
from homeassistant.helpers import config_validation as cv, template
from homeassistant.helpers.event import (
    TrackTemplate,
    async_call_later,
    async_track_template_result,
)
from homeassistant.helpers.template import result_as_boolean

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
    hass, config, action, automation_info, *, platform_type="template"
):
    """Listen for state changes based on configuration."""
    trigger_id = automation_info.get("trigger_id") if automation_info else None
    value_template = config.get(CONF_VALUE_TEMPLATE)
    value_template.hass = hass
    time_delta = config.get(CONF_FOR)
    template.attach(hass, time_delta)
    delay_cancel = None
    job = HassJob(action)
    armed = False

    # Arm at setup if the template is already false.
    try:
        if not result_as_boolean(
            value_template.async_render(automation_info["variables"])
        ):
            armed = True
    except exceptions.TemplateError as ex:
        _LOGGER.warning(
            "Error initializing 'template' trigger for '%s': %s",
            automation_info["name"],
            ex,
        )

    @callback
    def template_listener(event, updates):
        """Listen for state changes and calls action."""
        nonlocal delay_cancel, armed
        result = updates.pop().result

        if isinstance(result, exceptions.TemplateError):
            _LOGGER.warning(
                "Error evaluating 'template' trigger for '%s': %s",
                automation_info["name"],
                result,
            )
            return

        if delay_cancel:
            # pylint: disable=not-callable
            delay_cancel()
            delay_cancel = None

        if not result_as_boolean(result):
            armed = True
            return

        # Only fire when previously armed.
        if not armed:
            return

        # Fire!
        armed = False

        entity_id = event and event.data.get("entity_id")
        from_s = event and event.data.get("old_state")
        to_s = event and event.data.get("new_state")

        if entity_id is not None:
            description = f"{entity_id} via template"
        else:
            description = "time change or manual update via template"

        template_variables = {
            "platform": platform_type,
            "entity_id": entity_id,
            "from_state": from_s,
            "to_state": to_s,
        }
        trigger_variables = {
            "for": time_delta,
            "description": description,
            "id": trigger_id,
        }

        @callback
        def call_action(*_):
            """Call action with right context."""
            nonlocal trigger_variables
            hass.async_run_hass_job(
                job,
                {"trigger": {**template_variables, **trigger_variables}},
                (to_s.context if to_s else None),
            )

        if not time_delta:
            call_action()
            return

        try:
            period = cv.positive_time_period(
                template.render_complex(time_delta, {"trigger": template_variables})
            )
        except (exceptions.TemplateError, vol.Invalid) as ex:
            _LOGGER.error(
                "Error rendering '%s' for template: %s", automation_info["name"], ex
            )
            return

        trigger_variables["for"] = period

        delay_cancel = async_call_later(hass, period.seconds, call_action)

    info = async_track_template_result(
        hass,
        [TrackTemplate(value_template, automation_info["variables"])],
        template_listener,
    )
    unsub = info.async_remove

    @callback
    def async_remove():
        """Remove state listeners async."""
        unsub()
        if delay_cancel:
            # pylint: disable=not-callable
            delay_cancel()

    return async_remove
