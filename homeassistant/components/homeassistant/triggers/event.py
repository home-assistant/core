"""Offer event listening automation rules."""
import voluptuous as vol

from homeassistant.const import CONF_EVENT_DATA, CONF_PLATFORM
from homeassistant.core import HassJob, callback
from homeassistant.helpers import config_validation as cv, template

# mypy: allow-untyped-defs

CONF_EVENT_TYPE = "event_type"
CONF_EVENT_CONTEXT = "context"

TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM): "event",
        vol.Required(CONF_EVENT_TYPE): vol.All(cv.ensure_list, [cv.template]),
        vol.Optional(CONF_EVENT_DATA): vol.All(dict, cv.template_complex),
        vol.Optional(CONF_EVENT_CONTEXT): vol.All(dict, cv.template_complex),
    }
)


def _schema_value(value):
    if isinstance(value, list):
        return vol.In(value)

    return value


async def async_attach_trigger(
    hass, config, action, automation_info, *, platform_type="event"
):
    """Listen for events based on configuration."""
    trigger_id = automation_info.get("trigger_id") if automation_info else None
    variables = None
    if automation_info:
        variables = automation_info.get("variables")

    template.attach(hass, config[CONF_EVENT_TYPE])
    event_types = template.render_complex(
        config[CONF_EVENT_TYPE], variables, limited=True
    )
    removes = []

    event_data_schema = None
    if CONF_EVENT_DATA in config:
        # Render the schema input
        template.attach(hass, config[CONF_EVENT_DATA])
        event_data = {}
        event_data.update(
            template.render_complex(config[CONF_EVENT_DATA], variables, limited=True)
        )
        # Build the schema
        event_data_schema = vol.Schema(
            {vol.Required(key): value for key, value in event_data.items()},
            extra=vol.ALLOW_EXTRA,
        )

    event_context_schema = None
    if CONF_EVENT_CONTEXT in config:
        # Render the schema input
        template.attach(hass, config[CONF_EVENT_CONTEXT])
        event_context = {}
        event_context.update(
            template.render_complex(config[CONF_EVENT_CONTEXT], variables, limited=True)
        )
        # Build the schema
        event_context_schema = vol.Schema(
            {
                vol.Required(key): _schema_value(value)
                for key, value in event_context.items()
            },
            extra=vol.ALLOW_EXTRA,
        )

    job = HassJob(action)

    @callback
    def handle_event(event):
        """Listen for events and calls the action when data matches."""
        try:
            # Check that the event data and context match the configured
            # schema if one was provided
            if event_data_schema:
                event_data_schema(event.data)
            if event_context_schema:
                event_context_schema(event.context.as_dict())
        except vol.Invalid:
            # If event doesn't match, skip event
            return

        hass.async_run_hass_job(
            job,
            {
                "trigger": {
                    "platform": platform_type,
                    "event": event,
                    "description": f"event '{event.event_type}'",
                    "id": trigger_id,
                }
            },
            event.context,
        )

    removes = [
        hass.bus.async_listen(event_type, handle_event) for event_type in event_types
    ]

    @callback
    def remove_listen_events():
        """Remove event listeners."""
        for remove in removes:
            remove()

    return remove_listen_events
