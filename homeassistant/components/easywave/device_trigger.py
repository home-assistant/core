"""Device triggers for the Easywave integration."""

from typing import Any

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
    CONF_BUTTON_COUNT,
    CONF_ENTRY_TYPE,
    CONF_GROUPING_MODE,
    CONF_SWITCH_MODE,
    DOMAIN,
    ENTRY_TYPE_TRANSMITTER,
    EVENT_EASYWAVE,
    TRANSMITTER_GROUPING_GROUP,
)

_BATTERY_TRIGGER_TYPES = ("battery_low", "battery_normal")
# Type-1 group mode: state_a / state_b / state_c / state_d / state_released
_GROUP_STATE_TYPES = (
    "state_a",
    "state_b",
    "state_c",
    "state_d",
    "state_released",
)
# Gateway device connectivity triggers
_GATEWAY_TRIGGER_TYPES = ("gateway_connected", "gateway_disconnected")

ALL_TRIGGER_TYPES: set[str] = {
    *_BATTERY_TRIGGER_TYPES,
    *_GROUP_STATE_TYPES,
    *_GATEWAY_TRIGGER_TYPES,
}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_DOMAIN): DOMAIN,
        vol.Required(CONF_DEVICE_ID): str,
        vol.Required(CONF_TYPE): vol.In(ALL_TRIGGER_TYPES),
    }
)


def _get_transmitter_device_data(
    hass: HomeAssistant, device_id: str
) -> dict[str, Any] | None:
    """Return the stored transmitter device data for a HA device id, or None."""
    data = _get_device_data(hass, device_id)
    if data is None or data.get(CONF_ENTRY_TYPE) != ENTRY_TYPE_TRANSMITTER:
        return None
    return data


def _get_device_data(hass: HomeAssistant, device_id: str) -> dict[str, Any] | None:
    """Return the stored Easywave device data (any type) for a HA device id."""
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(device_id)
    if device_entry is None:
        return None

    subentry_id = next(
        (ident[1] for ident in device_entry.identifiers if ident[0] == DOMAIN),
        None,
    )
    if subentry_id is None:
        return None

    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id not in device_entry.config_entries:
            continue
        for device in entry.options.get("devices", []):
            if device.get("id") != subentry_id:
                continue
            return device.get("data", {})
    return None


def _is_gateway_device(hass: HomeAssistant, device_id: str) -> bool:
    """Return True if the device is the Easywave RX11 gateway device."""
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(device_id)
    if device_entry is None:
        return False
    entry_ids = {entry.entry_id for entry in hass.config_entries.async_entries(DOMAIN)}
    return any(
        ident[0] == DOMAIN and ident[1] in entry_ids
        for ident in device_entry.identifiers
    )


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List device triggers for an Easywave device."""
    base = {
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DOMAIN,
        CONF_DEVICE_ID: device_id,
    }

    if _is_gateway_device(hass, device_id):
        return [{**base, CONF_TYPE: t} for t in _GATEWAY_TRIGGER_TYPES]

    data = _get_transmitter_device_data(hass, device_id)
    if data is None:
        return []

    button_count = min(int(data.get(CONF_BUTTON_COUNT, 4)), 4)
    grouping_mode = str(data.get(CONF_GROUPING_MODE, "single"))

    if grouping_mode != TRANSMITTER_GROUPING_GROUP:
        return []

    # Group mode: one sensor whose value cycles through a/b/c/d/released.
    group_types = [f"state_{letter}" for letter in "abcd"[:button_count]]
    # "state_released" only applies in impulse mode; permanent mode
    # keeps the last state and never fires a release event.
    switch_mode = str(data.get(CONF_SWITCH_MODE, "impulse"))
    if switch_mode == "impulse":
        group_types.append("state_released")

    triggers = [{**base, CONF_TYPE: t} for t in group_types]
    triggers.extend({**base, CONF_TYPE: t} for t in _BATTERY_TRIGGER_TYPES)
    return triggers


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    config = TRIGGER_SCHEMA(config)
    device_id = config[CONF_DEVICE_ID]
    if _get_transmitter_device_data(hass, device_id) is None and not _is_gateway_device(
        hass, device_id
    ):
        raise InvalidDeviceAutomationConfig(
            f"Device ID {device_id} is not a valid Easywave device"
        )
    return config


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger by listening for the integration's HA event."""
    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: CONF_EVENT,
            event_trigger.CONF_EVENT_TYPE: EVENT_EASYWAVE,
            event_trigger.CONF_EVENT_DATA: {
                CONF_DEVICE_ID: config[CONF_DEVICE_ID],
                CONF_TYPE: config[CONF_TYPE],
            },
        }
    )
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )
