"""Provides device triggers for Lutron keypads."""

from __future__ import annotations

from typing import Any, cast

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

from . import (
    ATTR_ACTION,
    ATTR_BUTTON_SUBTYPE,
    ATTR_KEYPAD_UUID,
    LutronConfigEntry,
    button_subtype,
)
from .const import DOMAIN
from .event import LEGACY_EVENT_TYPES, LutronEventType

CONF_SUBTYPE = "subtype"

TRIGGER_ACTIONS = {
    LutronEventType.SINGLE_PRESS.value: LEGACY_EVENT_TYPES[
        LutronEventType.SINGLE_PRESS
    ],
    LutronEventType.PRESS.value: LEGACY_EVENT_TYPES[LutronEventType.PRESS],
    LutronEventType.RELEASE.value: LEGACY_EVENT_TYPES[LutronEventType.RELEASE],
}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_ACTIONS),
        vol.Required(CONF_SUBTYPE): str,
    }
)


def _keypad_identifier(controller_guid: str, keypad_uuid: str) -> tuple[str, str]:
    """Return the device registry identifier for a keypad."""
    return DOMAIN, f"{controller_guid}_{keypad_uuid}"


def _button_trigger_types(button_type: str | None) -> list[str]:
    """Return the trigger types supported by a button."""
    if button_type is not None and "RaiseLower" in button_type:
        return [LutronEventType.PRESS.value, LutronEventType.RELEASE.value]
    return [LutronEventType.SINGLE_PRESS.value]


def _get_entry_device_buttons(
    hass: HomeAssistant, device_id: str
) -> tuple[LutronConfigEntry, list[tuple[Any, Any]]] | None:
    """Return the config entry and keypad buttons for a device registry device."""
    device_registry = dr.async_get(hass)
    if (device := device_registry.async_get(device_id)) is None:
        return None

    device_identifiers = set(device.identifiers)
    for entry in cast(
        list[LutronConfigEntry],
        hass.config_entries.async_entries(
            DOMAIN, include_ignore=False, include_disabled=False
        ),
    ):
        if entry.entry_id not in device.config_entries or not hasattr(
            entry, "runtime_data"
        ):
            continue

        entry_buttons = [
            (keypad, button)
            for _area_name, keypad, button in entry.runtime_data.buttons
            if _keypad_identifier(
                entry.runtime_data.client.guid, keypad.uuid or keypad.legacy_uuid
            )
            in device_identifiers
        ]
        if entry_buttons:
            return entry, entry_buttons

    return None


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate a device trigger config."""
    config = TRIGGER_SCHEMA(config)

    found = _get_entry_device_buttons(hass, config[CONF_DEVICE_ID])
    if found is None:
        raise InvalidDeviceAutomationConfig(
            f"Device ID {config[CONF_DEVICE_ID]} is not a valid Lutron keypad"
        )

    _entry, buttons = found
    valid_triggers = {
        (trigger_type, button_subtype(keypad, button))
        for keypad, button in buttons
        for trigger_type in _button_trigger_types(button.button_type)
    }
    trigger_key = (config[CONF_TYPE], config[CONF_SUBTYPE])
    if trigger_key not in valid_triggers:
        raise InvalidDeviceAutomationConfig(
            f"Device does not support trigger {trigger_key}"
        )

    return config


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device triggers for a Lutron keypad."""
    found = _get_entry_device_buttons(hass, device_id)
    if found is None:
        return []

    _entry, buttons = found
    return [
        {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: trigger_type,
            CONF_SUBTYPE: button_subtype(keypad, button),
        }
        for keypad, button in buttons
        for trigger_type in _button_trigger_types(button.button_type)
    ]


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a device trigger."""
    config = await async_validate_trigger_config(hass, config)

    found = _get_entry_device_buttons(hass, config[CONF_DEVICE_ID])
    assert found is not None
    _entry, buttons = found

    for keypad, button in buttons:
        if button_subtype(keypad, button) != config[CONF_SUBTYPE]:
            continue

        event_config = event_trigger.TRIGGER_SCHEMA(
            {
                event_trigger.CONF_PLATFORM: CONF_EVENT,
                event_trigger.CONF_EVENT_TYPE: "lutron_event",
                event_trigger.CONF_EVENT_DATA: {
                    ATTR_ACTION: TRIGGER_ACTIONS[config[CONF_TYPE]],
                    ATTR_BUTTON_SUBTYPE: config[CONF_SUBTYPE],
                    ATTR_KEYPAD_UUID: keypad.uuid or keypad.legacy_uuid,
                },
            }
        )
        return await event_trigger.async_attach_trigger(
            hass, event_config, action, trigger_info, platform_type="device"
        )

    raise InvalidDeviceAutomationConfig(
        f"Unable to find button for trigger {config[CONF_TYPE]!r}/{config[CONF_SUBTYPE]!r}"
    )
