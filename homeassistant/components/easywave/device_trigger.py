"""Device triggers for the Easywave integration."""

from typing import Any

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.config_entries import ConfigEntry
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
    CONF_DEVICE_DATA,
    CONF_ENTRY_TYPE,
    CONF_SWITCH_MODE,
    DOMAIN,
    ENTRY_TYPE_TRANSMITTER,
    EVENT_EASYWAVE,
    EVENT_TYPE_BATTERY_LOW,
    EVENT_TYPE_BATTERY_NORMAL,
    EVENT_TYPE_BUTTON_PRESS,
    EVENT_TYPE_BUTTON_RELEASE,
    EVENT_TYPE_GATEWAY_CONNECTED,
    EVENT_TYPE_GATEWAY_DISCONNECTED,
    TRANSMITTER_SWITCH_IMPULSE,
)
from .devices import get_stored_devices

CONF_SUBTYPE = "subtype"

_BUTTON_SUBTYPES = ("a", "b", "c", "d")
_BATTERY_TRIGGER_TYPES = (EVENT_TYPE_BATTERY_LOW, EVENT_TYPE_BATTERY_NORMAL)
_GATEWAY_TRIGGER_TYPES = (
    EVENT_TYPE_GATEWAY_CONNECTED,
    EVENT_TYPE_GATEWAY_DISCONNECTED,
)
_TRANSMITTER_TRIGGER_TYPES = (
    EVENT_TYPE_BUTTON_PRESS,
    EVENT_TYPE_BUTTON_RELEASE,
    *_BATTERY_TRIGGER_TYPES,
)

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(
            _GATEWAY_TRIGGER_TYPES + _TRANSMITTER_TRIGGER_TYPES
        ),
        vol.Optional(CONF_SUBTYPE): str,
    }
)


def _device_identifier(device: dr.DeviceEntry) -> str | None:
    """Return the Easywave identifier stored on a device registry entry."""
    for domain, identifier in device.identifiers:
        if domain == DOMAIN:
            return identifier
    return None


class _GatewayMarker:
    """Sentinel value for the RX11 gateway device."""


_GATEWAY_MARKER = _GatewayMarker()


def _stored_device_data(entry: ConfigEntry, easywave_id: str) -> dict[str, Any] | None:
    """Return stored device data for a child device identifier."""
    for device in get_stored_devices(entry):
        if device.get(CONF_DEVICE_ID) != easywave_id:
            continue
        device_data = device.get(CONF_DEVICE_DATA)
        if not isinstance(device_data, dict):
            return None
        return dict(device_data)
    return None


def _find_easywave_config_entry(
    hass: HomeAssistant, device: dr.DeviceEntry
) -> ConfigEntry | None:
    """Return the Easywave config entry linked to a device."""
    device_registry = dr.async_get(hass)

    for entry_id in device.config_entries:
        if (entry := hass.config_entries.async_get_entry(entry_id)) and (
            entry.domain == DOMAIN
        ):
            return entry

    if device.via_device_id and (
        via_device := device_registry.async_get(device.via_device_id)
    ):
        for entry_id in via_device.config_entries:
            if (entry := hass.config_entries.async_get_entry(entry_id)) and (
                entry.domain == DOMAIN
            ):
                return entry

    easywave_id = _device_identifier(device)
    if easywave_id is None:
        return None

    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        if easywave_id == entry.entry_id:
            return entry
        if _stored_device_data(entry, easywave_id) is not None:
            return entry

    return None


def _get_device_data(
    hass: HomeAssistant, ha_device_id: str
) -> dict[str, Any] | _GatewayMarker | None:
    """Return device data from config entry options, or gateway marker."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(ha_device_id)
    if device is None:
        return None

    easywave_id = _device_identifier(device)
    if easywave_id is None:
        return None

    entry = _find_easywave_config_entry(hass, device)
    if entry is None:
        return None
    if easywave_id == entry.entry_id:
        return _GATEWAY_MARKER

    if device_data := _stored_device_data(entry, easywave_id):
        return device_data
    return None


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List device triggers for an Easywave gateway or transmitter."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    if device is None:
        return []
    if not any(identifier[0] == DOMAIN for identifier in device.identifiers):
        return []

    device_data = _get_device_data(hass, device_id)
    if device_data is None:
        return []

    if device_data is _GATEWAY_MARKER:
        return [
            {
                CONF_PLATFORM: "device",
                CONF_DOMAIN: DOMAIN,
                CONF_DEVICE_ID: device_id,
                CONF_TYPE: EVENT_TYPE_GATEWAY_CONNECTED,
                CONF_SUBTYPE: "connected",
            },
            {
                CONF_PLATFORM: "device",
                CONF_DOMAIN: DOMAIN,
                CONF_DEVICE_ID: device_id,
                CONF_TYPE: EVENT_TYPE_GATEWAY_DISCONNECTED,
                CONF_SUBTYPE: "disconnected",
            },
        ]

    assert isinstance(device_data, dict)
    if device_data.get(CONF_ENTRY_TYPE) != ENTRY_TYPE_TRANSMITTER:
        return []

    button_count = min(int(device_data.get(CONF_BUTTON_COUNT, 4)), 4)
    switch_mode = device_data.get(CONF_SWITCH_MODE, TRANSMITTER_SWITCH_IMPULSE)
    triggers: list[dict[str, Any]] = [
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: device_id,
            CONF_TYPE: EVENT_TYPE_BUTTON_PRESS,
            CONF_SUBTYPE: button,
        }
        for button in _BUTTON_SUBTYPES[:button_count]
    ]
    if switch_mode == TRANSMITTER_SWITCH_IMPULSE:
        triggers.append(
            {
                CONF_PLATFORM: "device",
                CONF_DOMAIN: DOMAIN,
                CONF_DEVICE_ID: device_id,
                CONF_TYPE: EVENT_TYPE_BUTTON_RELEASE,
                CONF_SUBTYPE: "released",
            }
        )
    triggers.extend(
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: device_id,
            CONF_TYPE: trigger_type,
            CONF_SUBTYPE: subtype,
        }
        for trigger_type, subtype in (
            (EVENT_TYPE_BATTERY_LOW, "low"),
            (EVENT_TYPE_BATTERY_NORMAL, "ok"),
        )
    )
    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a device trigger to an Easywave event."""
    event_data: dict[str, Any] = {
        "device_id": config[CONF_DEVICE_ID],
        "type": config[CONF_TYPE],
    }
    if CONF_SUBTYPE in config:
        event_data[CONF_SUBTYPE] = config[CONF_SUBTYPE]

    return await event_trigger.async_attach_trigger(
        hass,
        event_trigger.TRIGGER_SCHEMA(
            {
                event_trigger.CONF_PLATFORM: CONF_EVENT,
                event_trigger.CONF_EVENT_TYPE: EVENT_EASYWAVE,
                event_trigger.CONF_EVENT_DATA: event_data,
            }
        ),
        action,
        trigger_info,
        platform_type="device",
    )


async def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """Return trigger capabilities."""
    return {}
