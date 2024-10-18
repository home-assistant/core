"""Device triggers for Steam integrations."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import state as state_trigger
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import CONF_ACCOUNT, DOMAIN, TRIGGER_FRIEND_GAME_CHANGED

# Define the trigger types
TRIGGER_TYPES = {TRIGGER_FRIEND_GAME_CHANGED}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device triggers for Steam devices."""
    triggers = []
    base_trigger = {
        CONF_PLATFORM: "device",
        CONF_DEVICE_ID: device_id,
        CONF_DOMAIN: DOMAIN,
    }

    triggers += [
        {**base_trigger, CONF_TYPE: trigger_type} for trigger_type in TRIGGER_TYPES
    ]

    return triggers


def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""

    # Get the config entry for the Steam account based on device_id
    config_entry = hass.config_entries.async_get_entry(
        list(dr.async_get(hass).async_get(config[CONF_DEVICE_ID]).config_entries)[0]
    )

    # Find the primary entity id that's linked to the account on initial setup
    primary_user_entity_id = next(
        entity
        for entity in er.async_entries_for_device(
            er.async_get(hass), config[ATTR_DEVICE_ID]
        )
        if entity.unique_id == config_entry.data[CONF_ACCOUNT]
    ).entity_id

    # Get all sensor id's except the primary user
    friends_entity_ids = [
        entity.entity_id
        for entity in er.async_entries_for_device(
            er.async_get(hass), config[CONF_DEVICE_ID]
        )
        if entity.entity_id != primary_user_entity_id
    ]

    # Watch for game changes on all friends
    state_config = {
        state_trigger.CONF_PLATFORM: "device",
        state_trigger.CONF_ENTITY_ID: friends_entity_ids,
        state_trigger.CONF_ATTRIBUTE: "game_id",
    }

    return state_trigger.async_attach_trigger(
        hass,
        state_config,
        action,
        trigger_info,
    )
