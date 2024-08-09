"""Provides device triggers for event entities."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.device_automation import (
    DEVICE_TRIGGER_BASE_SCHEMA,
    async_get_entity_registry_entry_or_raise,
)
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TYPE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HassJob,
    HomeAssistant,
    callback,
)
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    translation,
)
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_EVENT_TYPE,
    ATTR_EVENT_TYPES,
    CONF_EVENT_TYPE,
    CONF_SUBTYPE,
    DOMAIN,
)

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id_or_uuid,
        vol.Required(CONF_TYPE): "event",
        vol.Required(CONF_SUBTYPE): str,
        vol.Required(CONF_EVENT_TYPE): str,
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List device triggers."""
    device_registry = dr.async_get(hass)
    if device_registry.async_get(device_id) is None:
        raise InvalidDeviceAutomationConfig(f"Device ID {device_id} is not valid")

    return [
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: device_id,
            CONF_ENTITY_ID: entity.id,
            CONF_TYPE: "event",
            CONF_SUBTYPE: _async_translate_event_type(
                hass,
                event_type,
                entity.domain,
                entity.platform,
                entity.translation_key,
                entity.device_class,
            ),
            CONF_EVENT_TYPE: event_type,
        }
        for entity in er.async_entries_for_device(er.async_get(hass), device_id)
        if entity.domain == DOMAIN and entity.capabilities
        for event_type in entity.capabilities.get(ATTR_EVENT_TYPES, [])
    ]


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Listen for state changes based on configuration."""
    trigger_data = trigger_info["trigger_data"]
    entity_id = async_get_entity_registry_entry_or_raise(
        hass, config[CONF_ENTITY_ID]
    ).entity_id
    job = HassJob(action)

    @callback
    def event_automation_listener(event: Event[EventStateChangedData]) -> None:
        """Listen for state changes and calls action."""
        entity = event.data["entity_id"]
        from_state = event.data["old_state"]
        to_state = event.data["new_state"]

        if (
            to_state
            and to_state.state
            not in (
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            )
            and config[CONF_EVENT_TYPE] == to_state.attributes.get(ATTR_EVENT_TYPE)
        ):
            description = f"{entity} triggered {config[CONF_EVENT_TYPE]}"
            hass.async_run_hass_job(
                job,
                {
                    "trigger": {
                        **trigger_data,
                        "platform": "device",
                        "entity_id": entity,
                        "from_state": from_state,
                        "to_state": to_state,
                        CONF_EVENT_TYPE: config[CONF_EVENT_TYPE],
                        "description": description,
                    }
                },
                to_state.context if to_state else None,
            )

    return async_track_state_change_event(hass, entity_id, event_automation_listener)


@callback
def _async_translate_event_type(
    hass: HomeAssistant,
    event_type: str,
    domain: str,
    platform: str | None,
    translation_key: str | None,
    device_class: str | None,
) -> str:
    """Translate provided event type using cached translations for currently selected language."""
    language = hass.config.language
    if platform is not None and translation_key is not None:
        localize_key = f"component.{platform}.entity.{domain}.{translation_key}.state_attributes.event_type.state.{event_type}"
        translations = translation.async_get_cached_translations(
            hass, language, "entity"
        )
        if localize_key in translations:
            return translations[localize_key]

    translations = translation.async_get_cached_translations(
        hass, language, "entity_component"
    )
    localize_key = f"component.{domain}.entity_component.{"_" if device_class is None else device_class}.state_attributes.event_type.state.{event_type}"
    if localize_key in translations:
        return translations[localize_key]

    return event_type
