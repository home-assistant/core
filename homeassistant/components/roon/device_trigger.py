"""Provides device triggers for RoonLabs music player."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, ROON_EVENT, ROON_EVENT_VOLUME_DOWN, ROON_EVENT_VOLUME_UP

TRIGGER_TYPES = {
    ROON_EVENT_VOLUME_UP,
    ROON_EVENT_VOLUME_DOWN,
}

_LOGGER = logging.getLogger(__name__)

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List device triggers for RoonLabs music player devices."""

    registry = er.async_get(hass)
    triggers = []

    # Get all the integrations entities for this device

    for entry in er.async_entries_for_device(registry, device_id):
        # I needed to change this from entry.domain - because the domain was 'media_player'
        # Does this mean something else is being set wrongly in the roon integration?
        if entry.platform != DOMAIN:
            continue

        base_trigger = {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: entry.entity_id,
        }
        triggers.append({**base_trigger, CONF_TYPE: ROON_EVENT_VOLUME_UP})
        triggers.append({**base_trigger, CONF_TYPE: ROON_EVENT_VOLUME_DOWN})

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""

    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: ROON_EVENT,
            event_trigger.CONF_EVENT_DATA: {
                CONF_ENTITY_ID: config[CONF_ENTITY_ID],
                CONF_TYPE: config[CONF_TYPE],
            },
        }
    )
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )
