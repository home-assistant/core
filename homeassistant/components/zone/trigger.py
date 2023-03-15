"""Offer zone automation rules."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    CONF_ENTITY_ID,
    CONF_EVENT,
    CONF_PLATFORM,
    CONF_ZONE,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    HassJob,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers import (
    condition,
    config_validation as cv,
    entity_registry as er,
    location,
)
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

EVENT_ENTER = "enter"
EVENT_LEAVE = "leave"
DEFAULT_EVENT = EVENT_ENTER

_LOGGER = logging.getLogger(__name__)

_EVENT_DESCRIPTION = {EVENT_ENTER: "entering", EVENT_LEAVE: "leaving"}

_TRIGGER_SCHEMA = cv.TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): "zone",
        vol.Required(CONF_ENTITY_ID): cv.entity_ids_or_uuids,
        vol.Required(CONF_ZONE): cv.entity_id,
        vol.Required(CONF_EVENT, default=DEFAULT_EVENT): vol.Any(
            EVENT_ENTER, EVENT_LEAVE
        ),
    }
)


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate trigger config."""
    config = _TRIGGER_SCHEMA(config)
    registry = er.async_get(hass)
    config[CONF_ENTITY_ID] = er.async_validate_entity_ids(
        registry, config[CONF_ENTITY_ID]
    )
    return config


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
    *,
    platform_type: str = "zone",
) -> CALLBACK_TYPE:
    """Listen for state changes based on configuration."""
    trigger_data = trigger_info["trigger_data"]
    entity_id: list[str] = config[CONF_ENTITY_ID]
    zone_entity_id: str = config[CONF_ZONE]
    event: str = config[CONF_EVENT]
    job = HassJob(action)

    @callback
    def zone_automation_listener(zone_event: Event) -> None:
        """Listen for state changes and calls action."""
        entity = zone_event.data.get("entity_id")
        from_s: State | None = zone_event.data.get("old_state")
        to_s: State | None = zone_event.data.get("new_state")

        if (
            from_s
            and not location.has_location(from_s)
            or to_s
            and not location.has_location(to_s)
        ):
            return

        if not (zone_state := hass.states.get(zone_entity_id)):
            _LOGGER.warning(
                (
                    "Automation '%s' is referencing non-existing zone '%s' in a zone"
                    " trigger"
                ),
                trigger_info["name"],
                zone_entity_id,
            )
            return

        from_match = condition.zone(hass, zone_state, from_s) if from_s else False
        to_match = condition.zone(hass, zone_state, to_s) if to_s else False

        if (
            event == EVENT_ENTER
            and not from_match
            and to_match
            or event == EVENT_LEAVE
            and from_match
            and not to_match
        ):
            description = f"{entity} {_EVENT_DESCRIPTION[event]} {zone_state.attributes[ATTR_FRIENDLY_NAME]}"
            hass.async_run_hass_job(
                job,
                {
                    "trigger": {
                        **trigger_data,
                        "platform": platform_type,
                        "entity_id": entity,
                        "from_state": from_s,
                        "to_state": to_s,
                        "zone": zone_state,
                        "event": event,
                        "description": description,
                    }
                },
                to_s.context if to_s else None,
            )

    return async_track_state_change_event(hass, entity_id, zone_automation_listener)
