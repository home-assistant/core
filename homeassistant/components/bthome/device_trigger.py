"""Provides device triggers for BTHome BLE."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_EVENT,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import (
    BTHOME_BLE_EVENT,
    CONF_DISCOVERED_EVENT_CLASSES,
    CONF_SUBTYPE,
    DOMAIN,
    EVENT_CLASS,
    EVENT_CLASS_BUTTON,
    EVENT_CLASS_DIMMER,
    EVENT_TYPE,
)

TRIGGERS_BY_EVENT_CLASS = {
    EVENT_CLASS_BUTTON: {
        "press",
        "double_press",
        "triple_press",
        "long_press",
        "long_double_press",
        "long_triple_press",
    },
    EVENT_CLASS_DIMMER: {"rotate_left", "rotate_right"},
}

SCHEMA_BY_EVENT_CLASS = {
    EVENT_CLASS_BUTTON: DEVICE_TRIGGER_BASE_SCHEMA.extend(
        {
            vol.Required(CONF_TYPE): vol.In([EVENT_CLASS_BUTTON]),
            vol.Required(CONF_SUBTYPE): vol.In(
                TRIGGERS_BY_EVENT_CLASS[EVENT_CLASS_BUTTON]
            ),
        }
    ),
    EVENT_CLASS_DIMMER: DEVICE_TRIGGER_BASE_SCHEMA.extend(
        {
            vol.Required(CONF_TYPE): vol.In([EVENT_CLASS_DIMMER]),
            vol.Required(CONF_SUBTYPE): vol.In(
                TRIGGERS_BY_EVENT_CLASS[EVENT_CLASS_DIMMER]
            ),
        }
    ),
}


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate trigger config."""
    return SCHEMA_BY_EVENT_CLASS.get(config[CONF_TYPE], DEVICE_TRIGGER_BASE_SCHEMA)(
        config
    )


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """Return a list of triggers for BTHome BLE devices."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    assert device is not None
    config_entries = [
        hass.config_entries.async_get_entry(entry_id)
        for entry_id in device.config_entries
    ]
    bthome_config_entry = next(
        iter(entry for entry in config_entries if entry and entry.domain == DOMAIN),
        None,
    )
    assert bthome_config_entry is not None
    return [
        {
            # Required fields of TRIGGER_BASE_SCHEMA
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            # Required fields of TRIGGER_SCHEMA
            CONF_TYPE: event_class,
            CONF_SUBTYPE: event_type,
        }
        for event_class in bthome_config_entry.data.get(
            CONF_DISCOVERED_EVENT_CLASSES, []
        )
        for event_type in TRIGGERS_BY_EVENT_CLASS.get(event_class, [])
    ]


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    return await event_trigger.async_attach_trigger(
        hass,
        event_trigger.TRIGGER_SCHEMA(
            {
                event_trigger.CONF_PLATFORM: CONF_EVENT,
                event_trigger.CONF_EVENT_TYPE: BTHOME_BLE_EVENT,
                event_trigger.CONF_EVENT_DATA: {
                    CONF_DEVICE_ID: config[CONF_DEVICE_ID],
                    EVENT_CLASS: config[CONF_TYPE],
                    EVENT_TYPE: config[CONF_SUBTYPE],
                },
            }
        ),
        action,
        trigger_info,
        platform_type="device",
    )
