"""Provides device triggers for BTHome BLE."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.device_automation import (
    DEVICE_TRIGGER_BASE_SCHEMA,
    InvalidDeviceAutomationConfig,
)
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

EVENT_TYPES_BY_EVENT_CLASS = {
    EVENT_CLASS_BUTTON: {
        "press",
        "double_press",
        "triple_press",
        "long_press",
        "long_double_press",
        "long_triple_press",
        "hold_press",
    },
    EVENT_CLASS_DIMMER: {"rotate_left", "rotate_right"},
}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {vol.Required(CONF_TYPE): str, vol.Required(CONF_SUBTYPE): str}
)


def get_event_classes_by_device_id(hass: HomeAssistant, device_id: str) -> list[str]:
    """Get the supported event classes for a device.

    Events for BTHome BLE devices are dynamically discovered
    and stored in the device config entry when they are first seen.
    """
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    if TYPE_CHECKING:
        assert device is not None

    config_entries = [
        hass.config_entries.async_get_entry(entry_id)
        for entry_id in device.config_entries
    ]
    bthome_config_entry = next(
        entry for entry in config_entries if entry and entry.domain == DOMAIN
    )
    return bthome_config_entry.data.get(CONF_DISCOVERED_EVENT_CLASSES, [])


def get_event_types_by_event_class(event_class: str) -> set[str]:
    """Get the supported event types for an event class.

    If the device has multiple buttons they will have
    event classes like button_1 button_2, button_3, etc
    but if there is only one button then it will be
    button without a number postfix.
    """
    return EVENT_TYPES_BY_EVENT_CLASS.get(event_class.split("_")[0], set())


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate trigger config."""
    config = TRIGGER_SCHEMA(config)
    event_class = config[CONF_TYPE]
    event_type = config[CONF_SUBTYPE]
    device_id = config[CONF_DEVICE_ID]
    event_classes = get_event_classes_by_device_id(hass, device_id)

    if event_class not in event_classes:
        raise InvalidDeviceAutomationConfig(
            f"BTHome trigger {event_class} is not valid for device_id '{device_id}'"
        )

    if event_type not in get_event_types_by_event_class(event_class):
        raise InvalidDeviceAutomationConfig(
            f"BTHome trigger {event_type} is not valid for device_id '{device_id}'"
        )

    return config


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """Return a list of triggers for BTHome BLE devices."""
    event_classes = get_event_classes_by_device_id(hass, device_id)
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
        for event_class in event_classes
        for event_type in get_event_types_by_event_class(event_class)
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
