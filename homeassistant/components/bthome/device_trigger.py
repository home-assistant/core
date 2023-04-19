"""Provides device triggers for BTHome BLE."""
from __future__ import annotations

from dataclasses import dataclass
import logging
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
    CONF_DEVICE_KEY,
    CONF_EVENT_PROPERTIES,
    EVENT_PROPERTIES,
    EVENT_TYPE,
)

_LOGGER = logging.getLogger(__name__)

BUTTON_DEVICE_TRIGGERS = [
    {CONF_TYPE: "press", CONF_EVENT_PROPERTIES: None},
    {CONF_TYPE: "double_press", CONF_EVENT_PROPERTIES: None},
    {CONF_TYPE: "triple_press", CONF_EVENT_PROPERTIES: None},
    {CONF_TYPE: "long_press", CONF_EVENT_PROPERTIES: None},
    {CONF_TYPE: "long_double_press", CONF_EVENT_PROPERTIES: None},
    {CONF_TYPE: "long_triple_press", CONF_EVENT_PROPERTIES: None},
]

DIMMER_DEVICE_TRIGGERS = [
    {CONF_TYPE: "rotate_left", CONF_EVENT_PROPERTIES: None},
    {CONF_TYPE: "rotate_right", CONF_EVENT_PROPERTIES: None},
]

BUTTON_DEVICE_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(
            [trigger[CONF_TYPE] for trigger in BUTTON_DEVICE_TRIGGERS]
        ),
        vol.Optional(CONF_EVENT_PROPERTIES): vol.In(
            [trigger[CONF_EVENT_PROPERTIES] for trigger in BUTTON_DEVICE_TRIGGERS]
        ),
    }
)

DIMMER_DEVICE_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(
            [trigger[CONF_TYPE] for trigger in DIMMER_DEVICE_TRIGGERS]
        ),
        vol.Optional(CONF_EVENT_PROPERTIES): vol.In(
            [trigger[CONF_EVENT_PROPERTIES] for trigger in DIMMER_DEVICE_TRIGGERS]
        ),
    }
)


TRIGGER_SCHEMA = vol.Any(
    BUTTON_DEVICE_SCHEMA,
    DIMMER_DEVICE_SCHEMA,
)


@dataclass
class BTHomeTriggers:
    """Data class for BTHome triggers."""

    triggers: list[dict[str, Any]]
    schema: vol.Schema


BTHOME_TRIGGER_TYPES = {
    "button": BTHomeTriggers(
        triggers=BUTTON_DEVICE_TRIGGERS, schema=BUTTON_DEVICE_SCHEMA
    ),
    "dimmer": BTHomeTriggers(
        triggers=DIMMER_DEVICE_TRIGGERS, schema=DIMMER_DEVICE_SCHEMA
    ),
}


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate trigger config."""
    # device_id = config[CONF_DEVICE_ID]
    device_key = config[CONF_DEVICE_KEY]
    if bthome_triggers := _async_device_trigger_types(hass, device_key):
        return bthome_triggers.schema(config)
    return config


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """Return a list of triggers for BTHome BLE devices."""
    device_registry = dr.async_get(hass)
    device_registry.async_get(device_id)

    triggers = []
    # Check if bthome event is supported device trigger.
    # device_key = config[CONF_DEVICE_KEY]
    # if not (bthome_triggers := _async_device_trigger_types(hass, device_key)):
    #     return []

    triggers.append(
        {
            # Required fields of TRIGGER_BASE_SCHEMA
            CONF_PLATFORM: "device",
            CONF_DOMAIN: "mydomain",
            CONF_DEVICE_ID: device_id,
            # Required fields of TRIGGER_SCHEMA
            CONF_TYPE: "water_detected",
        }
    )

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""

    event_data = {
        CONF_DEVICE_ID: config[CONF_DEVICE_ID],
        EVENT_TYPE: config[CONF_TYPE],
        EVENT_PROPERTIES: config[CONF_EVENT_PROPERTIES],
    }
    return await event_trigger.async_attach_trigger(
        hass,
        event_trigger.TRIGGER_SCHEMA(
            {
                event_trigger.CONF_PLATFORM: CONF_EVENT,
                event_trigger.CONF_EVENT_TYPE: BTHOME_BLE_EVENT,
                event_trigger.CONF_EVENT_DATA: event_data,
            }
        ),
        action,
        trigger_info,
        platform_type="device",
    )


def _async_device_trigger_types(
    hass: HomeAssistant, device_key: str
) -> BTHomeTriggers | None:
    """Get available triggers for a given device key."""
    # device_registry = dr.async_get(hass)
    # device = device_registry.async_get(device_key)
    if device_key and (device_trigger_types := BTHOME_TRIGGER_TYPES.get(device_key)):
        return device_trigger_types
    return None
