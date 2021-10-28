"""Provides device triggers for LCN."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.automation import (
    AutomationActionType,
    AutomationTriggerInfo,
)
from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import DOMAIN
from .const import KEY_ACTIONS, SENDKEYS

TRIGGER_TYPES = {"transmitter", "transponder", "fingerprint", "sendkeys"}

LCN_DEVICE_TRIGGER_BASE_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES)}
)

ACCESS_CONTROL_SCHEMA = {vol.Optional("code"): vol.All(vol.Lower, cv.string)}
TRANSMITTER_SCHEMA = {
    **ACCESS_CONTROL_SCHEMA,
    vol.Optional("level"): cv.positive_int,
    vol.Optional("key"): cv.positive_int,
    vol.Optional("action"): vol.In([action.lower() for action in KEY_ACTIONS]),
}

SENDKEYS_SCHEMA = {
    vol.Optional("key"): vol.In([key.lower() for key in SENDKEYS]),
    vol.Optional("action"): vol.In([action.lower() for action in KEY_ACTIONS]),
}

TRIGGER_SCHEMA = vol.Any(
    LCN_DEVICE_TRIGGER_BASE_SCHEMA.extend(ACCESS_CONTROL_SCHEMA),
    LCN_DEVICE_TRIGGER_BASE_SCHEMA.extend(TRANSMITTER_SCHEMA),
    LCN_DEVICE_TRIGGER_BASE_SCHEMA.extend(SENDKEYS_SCHEMA),
)


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> list[dict]:
    """List device triggers for LCN devices."""
    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get(device_id)

    triggers: list[dict] = []
    if device.model.startswith("group"):
        return triggers

    base_trigger = {
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DOMAIN,
        CONF_DEVICE_ID: device_id,
    }

    triggers.append({**base_trigger, CONF_TYPE: "transmitter"})
    triggers.append({**base_trigger, CONF_TYPE: "transponder"})
    triggers.append({**base_trigger, CONF_TYPE: "fingerprint"})
    triggers.append({**base_trigger, CONF_TYPE: "sendkeys"})

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: AutomationActionType,
    automation_info: AutomationTriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    event_data = {CONF_DEVICE_ID: config[CONF_DEVICE_ID]}
    event_data.update(
        {
            key: config[key]
            for key in ("code", "level", "key", "action")
            if key in config
        }
    )

    event_config = event.TRIGGER_SCHEMA(
        {
            event.CONF_PLATFORM: "event",
            event.CONF_EVENT_TYPE: f"lcn_{config[CONF_TYPE]}",
            event.CONF_EVENT_DATA: event_data,
        }
    )

    return await event.async_attach_trigger(
        hass, event_config, action, automation_info, platform_type="device"
    )


async def async_get_trigger_capabilities(hass: HomeAssistant, config: dict) -> dict:
    """List trigger capabilities."""
    if config[CONF_TYPE] == "transmitter":
        return {"extra_fields": vol.Schema(TRANSMITTER_SCHEMA)}
    elif config[CONF_TYPE] == "transponder":
        return {"extra_fields": vol.Schema(ACCESS_CONTROL_SCHEMA)}
    elif config[CONF_TYPE] == "fingerprint":
        return {"extra_fields": vol.Schema(ACCESS_CONTROL_SCHEMA)}
    elif config[CONF_TYPE] == "sendkeys":
        return {"extra_fields": vol.Schema(SENDKEYS_SCHEMA)}
    return {}
