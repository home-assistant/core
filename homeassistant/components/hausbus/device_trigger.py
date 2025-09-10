"""Defines device_trigger of the haus-bus integration."""

from collections.abc import Awaitable, Callable
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.device_automation.trigger import (
    DEVICE_TRIGGER_BASE_SCHEMA,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from homeassistant.helpers.typing import ConfigType

LOGGER = logging.getLogger(__name__)

DOMAIN = "hausbus"

TRIGGER_TYPES = [
    "button_pressed",
    "button_released",
    "button_clicked",
    "button_double_clicked",
    "button_hold_start",
    "button_hold_end",
]

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required("type"): vol.In(TRIGGER_TYPES),
        vol.Required("subtype"): str,
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """Used by HA to read the device_trigger of a given device_id"""

    device_registry = async_get_device_registry(hass)
    device = device_registry.async_get(device_id)
    if device is None:
        return []

    inputs = hass.data.get(DOMAIN, {}).get(device_id, {}).get("inputs", [])

    if not isinstance(inputs, list) or not all(isinstance(i, str) for i in inputs):
        return []

    LOGGER.debug(f"Device {device_id} report inputs: {inputs}")

    return [
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_id,
            "type": trigger_type,
            "subtype": input_name,  # e.g. "Taster_1"
        }
        for trigger_type in TRIGGER_TYPES
        for input_name in inputs
    ]


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validates the Trigger-Schema."""
    try:
        return TRIGGER_SCHEMA(config)
    except vol.Invalid as err:
        raise HomeAssistantError(f"Invalid trigger config: {err}") from err


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: Callable[[dict[str, Any]], Awaitable[None]],
    trigger_info: dict[str, Any],
) -> CALLBACK_TYPE:
    """Connects event listener and automation."""

    event_type = f"{DOMAIN}_button_event"

    async def handle_event(event):
        if event.data.get("device_id") != config["device_id"]:
            return
        if event.data.get("type") != config["type"]:
            return
        if event.data.get("subtype") != config["subtype"]:
            return
        await action(
            {
                "platform": "device",
                "domain": DOMAIN,
                "device_id": config["device_id"],
                "type": config["type"],
                "subtype": config["subtype"],
            }
        )

    return hass.bus.async_listen(event_type, handle_event)
