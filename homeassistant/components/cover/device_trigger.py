"""Provides device automations for Cover."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import (
    numeric_state as numeric_state_trigger,
    state as state_trigger,
)
from homeassistant.const import (
    CONF_ABOVE,
    CONF_BELOW,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_FOR,
    CONF_PLATFORM,
    CONF_TYPE,
    CONF_VALUE_TEMPLATE,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity import get_supported_features
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from . import DOMAIN, CoverEntityFeature

POSITION_TRIGGER_TYPES = {"position", "tilt_position"}
STATE_TRIGGER_TYPES = {"opened", "closed", "opening", "closing"}

POSITION_TRIGGER_SCHEMA = vol.All(
    DEVICE_TRIGGER_BASE_SCHEMA.extend(
        {
            vol.Required(CONF_ENTITY_ID): cv.entity_id_or_uuid,
            vol.Required(CONF_TYPE): vol.In(POSITION_TRIGGER_TYPES),
            vol.Optional(CONF_ABOVE): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
            vol.Optional(CONF_BELOW): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
        }
    ),
    cv.has_at_least_one_key(CONF_BELOW, CONF_ABOVE),
)

STATE_TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id_or_uuid,
        vol.Required(CONF_TYPE): vol.In(STATE_TRIGGER_TYPES),
        vol.Optional(CONF_FOR): cv.positive_time_period_dict,
    }
)

TRIGGER_SCHEMA = vol.Any(POSITION_TRIGGER_SCHEMA, STATE_TRIGGER_SCHEMA)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device triggers for Cover devices."""
    registry = er.async_get(hass)
    triggers = []

    # Get all the integrations entities for this device
    for entry in er.async_entries_for_device(registry, device_id):
        if entry.domain != DOMAIN:
            continue

        supported_features = get_supported_features(hass, entry.entity_id)
        supports_open_close = supported_features & (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        )

        # Add triggers for each entity that belongs to this integration
        base_trigger = {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: entry.id,
        }

        if supports_open_close:
            triggers += [
                {
                    **base_trigger,
                    CONF_TYPE: trigger,
                }
                for trigger in STATE_TRIGGER_TYPES
            ]
        if supported_features & CoverEntityFeature.SET_POSITION:
            triggers.append(
                {
                    **base_trigger,
                    CONF_TYPE: "position",
                }
            )
        if supported_features & CoverEntityFeature.SET_TILT_POSITION:
            triggers.append(
                {
                    **base_trigger,
                    CONF_TYPE: "tilt_position",
                }
            )

    return triggers


async def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List trigger capabilities."""
    if config[CONF_TYPE] not in POSITION_TRIGGER_TYPES:
        return {
            "extra_fields": vol.Schema(
                {vol.Optional(CONF_FOR): cv.positive_time_period_dict}
            )
        }

    return {
        "extra_fields": vol.Schema(
            {
                vol.Optional(CONF_ABOVE, default=0): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=100)
                ),
                vol.Optional(CONF_BELOW, default=100): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=100)
                ),
            }
        )
    }


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    if config[CONF_TYPE] in STATE_TRIGGER_TYPES:
        if config[CONF_TYPE] == "opened":
            to_state = STATE_OPEN
        elif config[CONF_TYPE] == "closed":
            to_state = STATE_CLOSED
        elif config[CONF_TYPE] == "opening":
            to_state = STATE_OPENING
        elif config[CONF_TYPE] == "closing":
            to_state = STATE_CLOSING

        state_config = {
            CONF_PLATFORM: "state",
            CONF_ENTITY_ID: config[CONF_ENTITY_ID],
            state_trigger.CONF_TO: to_state,
        }
        if CONF_FOR in config:
            state_config[CONF_FOR] = config[CONF_FOR]
        state_config = await state_trigger.async_validate_trigger_config(
            hass, state_config
        )
        return await state_trigger.async_attach_trigger(
            hass, state_config, action, trigger_info, platform_type="device"
        )

    if config[CONF_TYPE] == "position":
        position = "current_position"
    if config[CONF_TYPE] == "tilt_position":
        position = "current_tilt_position"
    min_pos = config.get(CONF_ABOVE, -1)
    max_pos = config.get(CONF_BELOW, 101)
    value_template = f"{{{{ state.attributes.{position} }}}}"

    numeric_state_config = {
        CONF_PLATFORM: "numeric_state",
        CONF_ENTITY_ID: config[CONF_ENTITY_ID],
        CONF_BELOW: max_pos,
        CONF_ABOVE: min_pos,
        CONF_VALUE_TEMPLATE: value_template,
    }
    numeric_state_config = await numeric_state_trigger.async_validate_trigger_config(
        hass, numeric_state_config
    )
    return await numeric_state_trigger.async_attach_trigger(
        hass, numeric_state_config, action, trigger_info, platform_type="device"
    )
