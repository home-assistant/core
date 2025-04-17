"""Offer event listening automation rules."""

from __future__ import annotations

from collections.abc import ItemsView, Mapping
from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_EVENT_DATA, CONF_PLATFORM, EVENT_STATE_REPORTED
from homeassistant.core import CALLBACK_TYPE, Event, HassJob, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, template
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

CONF_EVENT_TYPE = "event_type"
CONF_EVENT_CONTEXT = "context"


def _validate_event_types(value: Any) -> Any:
    """Validate the event types.

    If the event types are templated, we check when attaching the trigger.
    """
    templates: list[template.Template] = value
    if any(tpl.is_static and tpl.template == EVENT_STATE_REPORTED for tpl in templates):
        raise vol.Invalid(f"Can't listen to {EVENT_STATE_REPORTED} in event trigger")
    return value


TRIGGER_SCHEMA = cv.TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): "event",
        vol.Required(CONF_EVENT_TYPE): vol.All(
            cv.ensure_list, [cv.template], _validate_event_types
        ),
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

    event_types = template.render_complex(
        config[CONF_EVENT_TYPE], variables, limited=True
    )
    if EVENT_STATE_REPORTED in event_types:
        raise HomeAssistantError(
            f"Can't listen to {EVENT_STATE_REPORTED} in event trigger"
        )
    event_data_schema: vol.Schema | None = None
    event_data_items: ItemsView | None = None
    if CONF_EVENT_DATA in config:
        # Render the schema input
        event_data = {}
        event_data.update(
            template.render_complex(config[CONF_EVENT_DATA], variables, limited=True)
        )

        def build_schema(data: dict[str, Any]) -> vol.Schema:
            schema = {}
            for key, value in data.items():
                if isinstance(value, dict):
                    schema[vol.Required(key)] = build_schema(value)
                else:
                    schema[vol.Required(key)] = value
            return vol.Schema(schema, extra=vol.ALLOW_EXTRA)

        # For performance reasons, we want to avoid using a voluptuous schema here unless required
        # Thus, if possible, we try to use a simple items comparison
        # For that, we explicitly do not check for list like the context data below since lists are
        # a special case only used for context data. (see test test_event_data_with_list)
        # Otherwise, we recursively build the schema (see test test_event_data_with_list_nested)
        if any(isinstance(value, dict) for value in event_data.values()):
            event_data_schema = build_schema(event_data)
        else:
            # Use a simple items comparison if possible
            event_data_items = event_data.items()

    event_context_schema: vol.Schema | None = None
    event_context_items: ItemsView | None = None
    if CONF_EVENT_CONTEXT in config:
        # Render the schema input
        event_context = {}
        event_context.update(
            template.render_complex(config[CONF_EVENT_CONTEXT], variables, limited=True)
        )
        # Build the schema or a an items view if the schema is simple
        # and does not contain lists. Lists are a special case to support
        # matching events by user_id. (see test test_if_fires_on_multiple_user_ids)
        # This can likely be optimized further in the future to handle the
        # multiple user_id case without requiring expensive schema
        # validation.
        if any(isinstance(value, list) for value in event_context.values()):
            event_context_schema = vol.Schema(
                {
                    vol.Required(key): _schema_value(value)
                    for key, value in event_context.items()
                },
                extra=vol.ALLOW_EXTRA,
            )
        else:
            # Use a simple items comparison if possible
            event_context_items = event_context.items()

    job = HassJob(action, f"event trigger {trigger_info}")

    @callback
    def filter_event(event_data: Mapping[str, Any]) -> bool:
        """Filter events."""
        try:
            # Check that the event data and context match the configured
            # schema if one was provided
            if event_data_items:
                # Fast path for simple items comparison
                if not (event_data.items() >= event_data_items):
                    return False
            elif event_data_schema:
                # Slow path for schema validation
                event_data_schema(event_data)
        except vol.Invalid:
            # If event doesn't match, skip event
            return False
        return True

    @callback
    def handle_event(event: Event) -> None:
        """Listen for events and calls the action when data matches."""
        if event_context_items:
            # Fast path for simple items comparison
            # This is safe because we do not mutate the event context
            if not (event.context._as_dict.items() >= event_context_items):  # noqa: SLF001
                return
        elif event_context_schema:
            try:
                # Slow path for schema validation
                # This is safe because we make a copy of the event context
                event_context_schema(dict(event.context._as_dict))  # noqa: SLF001
            except vol.Invalid:
                # If event doesn't match, skip event
                return

        hass.loop.call_soon(
            hass.async_run_hass_job,
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

    event_filter = filter_event if event_data_items or event_data_schema else None
    removes = [
        hass.bus.async_listen(event_type, handle_event, event_filter=event_filter)
        for event_type in event_types
    ]

    @callback
    def remove_listen_events() -> None:
        """Remove event listeners."""
        for remove in removes:
            remove()

    return remove_listen_events
