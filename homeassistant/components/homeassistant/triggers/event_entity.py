"""Offer event entity listening automation rules."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.const import CONF_PLATFORM
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HassJob,
    HomeAssistant,
    callback,
)
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

CONF_EVENT_TYPE = "event_type"
CONF_ENTITY_ID = "entity_id"

TRIGGER_SCHEMA = cv.TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): "event_entity",
        vol.Required(CONF_ENTITY_ID): cv.entity_ids_or_uuids,
        vol.Required(CONF_EVENT_TYPE): cv.match_all,
    }
)


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate trigger config."""
    if not isinstance(config, dict):
        raise vol.Invalid("Expected a dictionary")

    config = TRIGGER_SCHEMA(config)

    registry = er.async_get(hass)
    config[CONF_ENTITY_ID] = er.async_validate_entity_ids(
        registry, cv.entity_ids_or_uuids(config[CONF_ENTITY_ID])
    )

    return config


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
    *,
    platform_type: str = "event_entity",
) -> CALLBACK_TYPE:
    """Listen for state changes based on configuration."""
    entity_id = config[CONF_ENTITY_ID]
    event_type = config[CONF_EVENT_TYPE]

    job = HassJob(action, f"event trigger {trigger_info}")
    trigger_data = trigger_info["trigger_data"]

    @callback
    def state_automation_listener(event: Event[EventStateChangedData]) -> None:
        """Listen for state changes and calls action."""
        entity = event.data["entity_id"]
        from_s = event.data["old_state"]
        to_s = event.data["new_state"]

        if not from_s or from_s.state == "unavailable":
            return

        if not to_s or to_s.state in ("unavailable", "unknown"):
            return

        if to_s.attributes["event_type"] == event_type:
            hass.async_run_hass_job(
                job,
                {
                    "trigger": {
                        **trigger_data,
                        "platform": platform_type,
                        "entity_id": entity,
                        "event_type": event_type,
                        "description": f"{event_type} event of {entity}",
                    }
                },
                event.context,
            )

    unsub = async_track_state_change_event(hass, entity_id, state_automation_listener)

    @callback
    def async_remove() -> None:
        """Remove state listeners async."""
        unsub()

    return async_remove
