"""Device triggers for Flic Button integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_PUSH_TWIST_MODE,
    DOMAIN,
    EVENT_TYPE_CLICK,
    EVENT_TYPE_DOUBLE_CLICK,
    EVENT_TYPE_DOWN,
    EVENT_TYPE_DUO_DIAL_CHANGED,
    EVENT_TYPE_HOLD,
    EVENT_TYPE_PUSH_TWIST_DECREMENT,
    EVENT_TYPE_PUSH_TWIST_INCREMENT,
    EVENT_TYPE_ROTATE_CLOCKWISE,
    EVENT_TYPE_ROTATE_COUNTER_CLOCKWISE,
    EVENT_TYPE_SELECTOR_CHANGED,
    EVENT_TYPE_SLOT_CHANGED,
    EVENT_TYPE_SWIPE_DOWN,
    EVENT_TYPE_SWIPE_LEFT,
    EVENT_TYPE_SWIPE_RIGHT,
    EVENT_TYPE_SWIPE_UP,
    EVENT_TYPE_TWIST_DECREMENT,
    EVENT_TYPE_TWIST_INCREMENT,
    EVENT_TYPE_UP,
    FLIC_BUTTON_EVENT,
    PushTwistMode,
)
from .handlers import DeviceCapabilities

CONF_SUBTYPE = "subtype"

# Subtypes for different Flic devices
SUBTYPE_BUTTON = "button"  # Single button (Flic 2)
SUBTYPE_SMALL_BUTTON = "small_button"  # Small button (Duo, index 1)
SUBTYPE_BIG_BUTTON = "big_button"  # Big button (Duo, index 0)
SUBTYPE_TWIST_BUTTON = "twist_button"  # Twist button

# Map subtypes to button indices
SUBTYPE_TO_INDEX = {
    SUBTYPE_BUTTON: None,
    SUBTYPE_SMALL_BUTTON: 1,
    SUBTYPE_BIG_BUTTON: 0,
    SUBTYPE_TWIST_BUTTON: None,  # Twist has single button, no index needed
}

# Base event types available for all Flic buttons
FLIC_BASE_EVENT_TYPES = [
    EVENT_TYPE_UP,
    EVENT_TYPE_DOWN,
    EVENT_TYPE_CLICK,
    EVENT_TYPE_DOUBLE_CLICK,
    EVENT_TYPE_HOLD,
]

# Additional event types for Flic Duo (swipe gestures, rotation, and dial)
FLIC_DUO_EVENT_TYPES = [
    EVENT_TYPE_SWIPE_LEFT,
    EVENT_TYPE_SWIPE_RIGHT,
    EVENT_TYPE_SWIPE_UP,
    EVENT_TYPE_SWIPE_DOWN,
    EVENT_TYPE_ROTATE_CLOCKWISE,
    EVENT_TYPE_ROTATE_COUNTER_CLOCKWISE,
    EVENT_TYPE_DUO_DIAL_CHANGED,
]

# Event types for Flic Twist SELECTOR mode (rotation, selector, and slot changes)
FLIC_TWIST_SELECTOR_EVENT_TYPES = [
    EVENT_TYPE_ROTATE_CLOCKWISE,
    EVENT_TYPE_ROTATE_COUNTER_CLOCKWISE,
    EVENT_TYPE_SELECTOR_CHANGED,
    *EVENT_TYPE_SLOT_CHANGED,  # 12 slot change events
]

# Event types for Flic Twist DEFAULT mode (increment/decrement)
FLIC_TWIST_DEFAULT_EVENT_TYPES = [
    EVENT_TYPE_TWIST_INCREMENT,
    EVENT_TYPE_TWIST_DECREMENT,
    EVENT_TYPE_PUSH_TWIST_INCREMENT,
    EVENT_TYPE_PUSH_TWIST_DECREMENT,
]

# All event types (base + Duo + Twist SELECTOR + Twist DEFAULT)
FLIC_ALL_EVENT_TYPES = (
    FLIC_BASE_EVENT_TYPES
    + FLIC_DUO_EVENT_TYPES
    + FLIC_TWIST_SELECTOR_EVENT_TYPES
    + FLIC_TWIST_DEFAULT_EVENT_TYPES
)


def _get_device_capabilities_and_mode(
    hass: HomeAssistant, device_id: str
) -> tuple[DeviceCapabilities, PushTwistMode] | None:
    """Get device capabilities and push-twist mode from coordinator."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    if device is None:
        return None

    # Find config entry for this device
    for entry in hass.config_entries.async_entries(DOMAIN):
        # Check if entry has runtime_data (may not be loaded yet)
        if not hasattr(entry, "runtime_data") or entry.runtime_data is None:
            continue
        coordinator = entry.runtime_data
        if (DOMAIN, coordinator.client.address) in device.identifiers:
            push_twist_mode = PushTwistMode(
                entry.options.get(CONF_PUSH_TWIST_MODE, PushTwistMode.DEFAULT)
            )
            return coordinator.capabilities, push_twist_mode
    return None


def _get_event_types_for_capabilities(
    capabilities: DeviceCapabilities,
    push_twist_mode: PushTwistMode = PushTwistMode.DEFAULT,
) -> list[str]:
    """Get event types for device capabilities."""
    event_types = list(FLIC_BASE_EVENT_TYPES)

    if capabilities.has_gestures:
        # Gestures and dial are Duo-only features
        event_types.extend(
            [
                EVENT_TYPE_SWIPE_LEFT,
                EVENT_TYPE_SWIPE_RIGHT,
                EVENT_TYPE_SWIPE_UP,
                EVENT_TYPE_SWIPE_DOWN,
                EVENT_TYPE_ROTATE_CLOCKWISE,
                EVENT_TYPE_ROTATE_COUNTER_CLOCKWISE,
                EVENT_TYPE_DUO_DIAL_CHANGED,
            ]
        )
    elif capabilities.has_selector:
        # Twist device — event types depend on push-twist mode
        if push_twist_mode == PushTwistMode.SELECTOR:
            event_types.extend(FLIC_TWIST_SELECTOR_EVENT_TYPES)
        else:
            event_types.extend(FLIC_TWIST_DEFAULT_EVENT_TYPES)

    return event_types


TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(FLIC_ALL_EVENT_TYPES),
        vol.Required(CONF_SUBTYPE): vol.In(
            [
                SUBTYPE_BUTTON,
                SUBTYPE_SMALL_BUTTON,
                SUBTYPE_BIG_BUTTON,
                SUBTYPE_TWIST_BUTTON,
            ]
        ),
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List device triggers for Flic Button."""
    triggers: list[dict[str, Any]] = []

    # Try to get capabilities and mode from coordinator
    result = _get_device_capabilities_and_mode(hass, device_id)

    if result:
        capabilities, push_twist_mode = result
        # Use capabilities for trigger generation
        event_types = _get_event_types_for_capabilities(capabilities, push_twist_mode)

        if capabilities.button_count > 1:
            # Multi-button device (Duo) - create triggers for each button
            subtypes = [SUBTYPE_SMALL_BUTTON, SUBTYPE_BIG_BUTTON]
            for subtype in subtypes[: capabilities.button_count]:
                triggers.extend(
                    {
                        CONF_PLATFORM: "device",
                        CONF_DEVICE_ID: device_id,
                        CONF_DOMAIN: DOMAIN,
                        CONF_TYPE: event_type,
                        CONF_SUBTYPE: subtype,
                    }
                    for event_type in event_types
                )
        elif capabilities.has_selector:
            # Twist device
            triggers.extend(
                {
                    CONF_PLATFORM: "device",
                    CONF_DEVICE_ID: device_id,
                    CONF_DOMAIN: DOMAIN,
                    CONF_TYPE: event_type,
                    CONF_SUBTYPE: SUBTYPE_TWIST_BUTTON,
                }
                for event_type in event_types
            )
        else:
            # Single button device (Flic 2)
            triggers.extend(
                {
                    CONF_PLATFORM: "device",
                    CONF_DEVICE_ID: device_id,
                    CONF_DOMAIN: DOMAIN,
                    CONF_TYPE: event_type,
                    CONF_SUBTYPE: SUBTYPE_BUTTON,
                }
                for event_type in event_types
            )
    else:
        # Fallback: Use entity registry to detect device type
        entity_registry = er.async_get(hass)
        entries = er.async_entries_for_device(entity_registry, device_id)

        is_duo = any(
            entry.unique_id.endswith("_small") or entry.unique_id.endswith("_big")
            for entry in entries
        )
        is_twist = any(entry.unique_id.endswith("_twist") for entry in entries)

        if is_twist:
            # Determine push-twist mode from config entry options
            twist_event_types = FLIC_TWIST_DEFAULT_EVENT_TYPES
            for entry in hass.config_entries.async_entries(DOMAIN):
                push_twist_mode_str = entry.options.get(
                    CONF_PUSH_TWIST_MODE, PushTwistMode.DEFAULT
                )
                if PushTwistMode(push_twist_mode_str) == PushTwistMode.SELECTOR:
                    twist_event_types = FLIC_TWIST_SELECTOR_EVENT_TYPES
                break
            triggers.extend(
                {
                    CONF_PLATFORM: "device",
                    CONF_DEVICE_ID: device_id,
                    CONF_DOMAIN: DOMAIN,
                    CONF_TYPE: event_type,
                    CONF_SUBTYPE: SUBTYPE_TWIST_BUTTON,
                }
                for event_type in FLIC_BASE_EVENT_TYPES + twist_event_types
            )
        elif is_duo:
            for subtype in (SUBTYPE_SMALL_BUTTON, SUBTYPE_BIG_BUTTON):
                triggers.extend(
                    {
                        CONF_PLATFORM: "device",
                        CONF_DEVICE_ID: device_id,
                        CONF_DOMAIN: DOMAIN,
                        CONF_TYPE: event_type,
                        CONF_SUBTYPE: subtype,
                    }
                    for event_type in FLIC_BASE_EVENT_TYPES + FLIC_DUO_EVENT_TYPES
                )
        else:
            triggers.extend(
                {
                    CONF_PLATFORM: "device",
                    CONF_DEVICE_ID: device_id,
                    CONF_DOMAIN: DOMAIN,
                    CONF_TYPE: event_type,
                    CONF_SUBTYPE: SUBTYPE_BUTTON,
                }
                for event_type in FLIC_BASE_EVENT_TYPES
            )

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    # Build event data filter
    event_data: dict[str, Any] = {
        CONF_DEVICE_ID: config[CONF_DEVICE_ID],
        "event_type": config[CONF_TYPE],
    }

    # Add button_index filter for Duo buttons
    subtype = config.get(CONF_SUBTYPE)
    if subtype and subtype in SUBTYPE_TO_INDEX:
        button_index = SUBTYPE_TO_INDEX[subtype]
        if button_index is not None:
            event_data["button_index"] = button_index

    return await event_trigger.async_attach_trigger(
        hass,
        event_trigger.TRIGGER_SCHEMA(
            {
                event_trigger.CONF_PLATFORM: "event",
                event_trigger.CONF_EVENT_TYPE: FLIC_BUTTON_EVENT,
                event_trigger.CONF_EVENT_DATA: event_data,
            }
        ),
        action,
        trigger_info,
        platform_type="device",
    )


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate trigger config."""
    config_result: ConfigType = TRIGGER_SCHEMA(config)
    return config_result
