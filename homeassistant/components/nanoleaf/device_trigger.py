"""Provides device triggers for Nanoleaf."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.device_automation.exceptions import DeviceNotFound
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_EVENT,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import device_registry as dr, selector
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from . import NanoleafEntryData
from .const import (
    DOMAIN,
    NANOLEAF_EVENT,
    NANOLEAF_PANEL_ID,
    TOUCH_GESTURE_TRIGGER_MAP,
    TOUCH_MODELS,
)

TRIGGER_TYPES = TOUCH_GESTURE_TRIGGER_MAP.values()
TRIGGER_TYPES_THAT_REPORT_PANEL_ID = [p for p in TRIGGER_TYPES if p.endswith("_tap")]

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_DOMAIN): DOMAIN,
        vol.Required(CONF_DEVICE_ID): str,
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
        vol.Optional(NANOLEAF_PANEL_ID): vol.Coerce(int),
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device triggers for Nanoleaf devices."""
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(device_id)
    if device_entry is None:
        raise DeviceNotFound(f"Device ID {device_id} is not valid")
    if device_entry.model not in TOUCH_MODELS:
        return []
    return [
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: device_id,
            CONF_TYPE: trigger_type,
        }
        for trigger_type in TRIGGER_TYPES
    ]


async def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List trigger capabilities."""
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(config[CONF_DEVICE_ID])
    if device_entry is None:
        raise DeviceNotFound(f"Device ID {config[CONF_DEVICE_ID]} is not valid")
    if config[CONF_TYPE] in TRIGGER_TYPES_THAT_REPORT_PANEL_ID:
        entryData: NanoleafEntryData = hass.data[DOMAIN][
            next(iter(device_entry.config_entries))
        ]
        panels = entryData.device.panels
        options = [
            selector.SelectOptionDict(value=str(p.id), label=f"{p.id} - {p.shape.name}")
            for p in panels
            if p.id is not None
        ]
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Optional(NANOLEAF_PANEL_ID): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            multiple=False,
                            custom_value=True,
                            options=options,
                        )
                    )
                }
            )
        }

    return {}


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: CONF_EVENT,
            event_trigger.CONF_EVENT_TYPE: NANOLEAF_EVENT,
            event_trigger.CONF_EVENT_DATA: {
                CONF_TYPE: config[CONF_TYPE],
                CONF_DEVICE_ID: config[CONF_DEVICE_ID],
                NANOLEAF_PANEL_ID: (
                    config[NANOLEAF_PANEL_ID] if NANOLEAF_PANEL_ID in config else None
                ),
            },
        }
    )
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )
