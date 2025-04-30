"""Provides device triggers for Shelly."""

from __future__ import annotations

from typing import Final

import voluptuous as vol

from homeassistant.components.device_automation import (
    DEVICE_TRIGGER_BASE_SCHEMA,
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_EVENT,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_CHANNEL,
    ATTR_CLICK_TYPE,
    BLOCK_INPUTS_EVENTS_TYPES,
    CONF_SUBTYPE,
    DOMAIN,
    EVENT_SHELLY_CLICK,
    INPUTS_EVENTS_SUBTYPES,
    RPC_INPUTS_EVENTS_TYPES,
    SHBTN_MODELS,
)
from .coordinator import (
    get_block_coordinator_by_device_id,
    get_rpc_coordinator_by_device_id,
)
from .utils import (
    get_block_input_triggers,
    get_rpc_input_triggers,
    get_shbtn_input_triggers,
)

TRIGGER_SCHEMA: Final = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(
            RPC_INPUTS_EVENTS_TYPES | BLOCK_INPUTS_EVENTS_TYPES
        ),
        vol.Required(CONF_SUBTYPE): vol.In(INPUTS_EVENTS_SUBTYPES),
    }
)


def append_input_triggers(
    triggers: list[dict[str, str]],
    input_triggers: list[tuple[str, str]],
    device_id: str,
) -> None:
    """Add trigger to triggers list."""
    for trigger, subtype in input_triggers:
        triggers.append(
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_TYPE: trigger,
                CONF_SUBTYPE: subtype,
            }
        )


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    config = TRIGGER_SCHEMA(config)

    # if device is available verify parameters against device capabilities
    trigger = (config[CONF_TYPE], config[CONF_SUBTYPE])

    if config[CONF_TYPE] in RPC_INPUTS_EVENTS_TYPES:
        rpc_coordinator = get_rpc_coordinator_by_device_id(hass, config[CONF_DEVICE_ID])
        if not rpc_coordinator or not rpc_coordinator.device.initialized:
            return config

        input_triggers = get_rpc_input_triggers(rpc_coordinator.device)
        if trigger in input_triggers:
            return config

    elif config[CONF_TYPE] in BLOCK_INPUTS_EVENTS_TYPES:
        block_coordinator = get_block_coordinator_by_device_id(
            hass, config[CONF_DEVICE_ID]
        )
        if not block_coordinator or not block_coordinator.device.initialized:
            return config

        assert block_coordinator.device.blocks

        for block in block_coordinator.device.blocks:
            input_triggers = get_block_input_triggers(block_coordinator.device, block)
            if trigger in input_triggers:
                return config

    raise InvalidDeviceAutomationConfig(
        translation_domain=DOMAIN,
        translation_key="invalid_trigger",
        translation_placeholders={"trigger": str(trigger)},
    )


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device triggers for Shelly devices."""
    triggers: list[dict[str, str]] = []

    if rpc_coordinator := get_rpc_coordinator_by_device_id(hass, device_id):
        input_triggers = get_rpc_input_triggers(rpc_coordinator.device)
        append_input_triggers(triggers, input_triggers, device_id)
        return triggers

    if block_coordinator := get_block_coordinator_by_device_id(hass, device_id):
        if block_coordinator.model in SHBTN_MODELS:
            input_triggers = get_shbtn_input_triggers()
            append_input_triggers(triggers, input_triggers, device_id)
            return triggers

        if not block_coordinator.device.initialized:
            return triggers

        assert block_coordinator.device.blocks

        for block in block_coordinator.device.blocks:
            input_triggers = get_block_input_triggers(block_coordinator.device, block)
            append_input_triggers(triggers, input_triggers, device_id)

        return triggers

    raise InvalidDeviceAutomationConfig(
        translation_domain=DOMAIN,
        translation_key="device_not_found",
        translation_placeholders={"device": device_id},
    )


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    event_config = {
        event_trigger.CONF_PLATFORM: CONF_EVENT,
        event_trigger.CONF_EVENT_TYPE: EVENT_SHELLY_CLICK,
        event_trigger.CONF_EVENT_DATA: {
            ATTR_DEVICE_ID: config[CONF_DEVICE_ID],
            ATTR_CHANNEL: INPUTS_EVENTS_SUBTYPES[config[CONF_SUBTYPE]],
            ATTR_CLICK_TYPE: config[CONF_TYPE],
        },
    }

    event_config = event_trigger.TRIGGER_SCHEMA(event_config)
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )
