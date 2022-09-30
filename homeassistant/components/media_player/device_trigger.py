"""Provides device automations for Media player."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.device_automation import (
    DEVICE_TRIGGER_BASE_SCHEMA,
    entity,
)
from homeassistant.components.homeassistant.triggers import state as state_trigger
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_FOR,
    CONF_PLATFORM,
    CONF_TYPE,
    STATE_BUFFERING,
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

TRIGGER_TYPES = {"turned_on", "turned_off", "buffering", "idle", "paused", "playing"}

MEDIA_PLAYER_TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
        vol.Optional(CONF_FOR): cv.positive_time_period_dict,
    }
)

TRIGGER_SCHEMA = vol.All(
    vol.Any(
        MEDIA_PLAYER_TRIGGER_SCHEMA,
        entity.TRIGGER_SCHEMA,
    ),
    vol.Schema({vol.Required(CONF_DOMAIN): DOMAIN}, extra=vol.ALLOW_EXTRA),
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device triggers for Media player entities."""
    registry = entity_registry.async_get(hass)
    triggers = await entity.async_get_triggers(hass, device_id, DOMAIN)

    # Get all the integration entities for this device
    for entry in entity_registry.async_entries_for_device(registry, device_id):
        if entry.domain != DOMAIN:
            continue

        # Add triggers for each entity that belongs to this integration
        triggers += [
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: trigger,
            }
            for trigger in TRIGGER_TYPES
        ]

    return triggers


async def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List trigger capabilities."""
    if config[CONF_TYPE] not in TRIGGER_TYPES:
        return await entity.async_get_trigger_capabilities(hass, config)
    return {
        "extra_fields": vol.Schema(
            {vol.Optional(CONF_FOR): cv.positive_time_period_dict}
        )
    }


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    if config[CONF_TYPE] not in TRIGGER_TYPES:
        return await entity.async_attach_trigger(hass, config, action, trigger_info)
    if config[CONF_TYPE] == "buffering":
        to_state = STATE_BUFFERING
    elif config[CONF_TYPE] == "idle":
        to_state = STATE_IDLE
    elif config[CONF_TYPE] == "turned_off":
        to_state = STATE_OFF
    elif config[CONF_TYPE] == "turned_on":
        to_state = STATE_ON
    elif config[CONF_TYPE] == "paused":
        to_state = STATE_PAUSED
    else:  # "playing"
        to_state = STATE_PLAYING

    state_config = {
        CONF_PLATFORM: "state",
        CONF_ENTITY_ID: config[CONF_ENTITY_ID],
        state_trigger.CONF_TO: to_state,
    }
    if CONF_FOR in config:
        state_config[CONF_FOR] = config[CONF_FOR]
    state_config = await state_trigger.async_validate_trigger_config(hass, state_config)
    return await state_trigger.async_attach_trigger(
        hass, state_config, action, trigger_info, platform_type="device"
    )
