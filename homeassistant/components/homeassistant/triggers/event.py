"""Offer event listening automation rules."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_EVENT_DATA, CONF_PLATFORM
from homeassistant.core import CALLBACK_TYPE, Event, HassJob, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, template
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

CONF_EVENT_TYPE = "event_type"
CONF_EVENT_CONTEXT = "context"

TRIGGER_SCHEMA = cv.TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): "event",
        vol.Required(CONF_EVENT_TYPE): vol.All(cv.ensure_list, [cv.template]),
        vol.Optional(CONF_EVENT_DATA): vol.All(dict, cv.template_complex),
        vol.Optional(CONF_EVENT_CONTEXT): vol.All(dict, cv.template_complex),
    }
)


def _schema_value(value: Any) -> Any:
    if isinstance(value, list):
        return vol.In(value)

    return value


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
    *,
    platform_type: str = "event",
) -> CALLBACK_TYPE:
    """Listen for events based on configuration."""
    trigger_data = trigger_info["trigger_data"]
    variables = trigger_info["variables"]

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

    job = HassJob(action, f"event trigger {trigger_info}")

    @callback
    def filter_event(event: Event) -> bool:
        """Filter events."""
        try:
            # Check that the event data and context match the configured
            # schema if one was provided
            if event_data_schema:
                event_data_schema(event.data)
            if event_context_schema:
                event_context_schema(event.context.as_dict())
        except vol.Invalid:
            # If event doesn't match, skip event
            return False
        return True

    @callback
    def handle_event(event: Event) -> None:
        """Listen for events and calls the action when data matches."""
        hass.async_run_hass_job(
            job,
            {
                "trigger": {
                    **trigger_data,
                    "platform": platform_type,
                    "event": event,
                    "description": f"event '{event.event_type}'",
                }
            },
            event.context,
        )

    removes = [
        hass.bus.async_listen(event_type, handle_event, event_filter=filter_event)
        for event_type in event_types
    ]

    @callback
    def remove_listen_events() -> None:
        """Remove event listeners."""
        for remove in removes:
            remove()

    return remove_listen_events
