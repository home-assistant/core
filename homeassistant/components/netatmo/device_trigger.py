"""Provides device automations for Netatmo."""
from typing import List

import voluptuous as vol

from homeassistant.components.automation import AutomationActionType
from homeassistant.components.device_automation import TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry
from homeassistant.helpers.typing import ConfigType

from . import DOMAIN
from .const import (
    EVENT_TYPE_CAMERA_ANIMAL,
    EVENT_TYPE_CAMERA_HUMAN,
    EVENT_TYPE_CAMERA_MOVEMENT,
    EVENT_TYPE_CAMERA_OUTDOOR,
    EVENT_TYPE_CAMERA_PERSON,
    EVENT_TYPE_CAMERA_PERSON_AWAY,
    EVENT_TYPE_CAMERA_VEHICLE,
    MODEL_NACAMERA,
    MODEL_NOC,
)

OUTDOOR_CAMERA_TRIGGERS = [
    EVENT_TYPE_CAMERA_ANIMAL,
    EVENT_TYPE_CAMERA_HUMAN,
    EVENT_TYPE_CAMERA_OUTDOOR,
    EVENT_TYPE_CAMERA_VEHICLE,
]
INDOOR_CAMERA_TRIGGERS = [
    EVENT_TYPE_CAMERA_MOVEMENT,
    EVENT_TYPE_CAMERA_PERSON,
    EVENT_TYPE_CAMERA_PERSON_AWAY,
]

DEVICES = {
    MODEL_NACAMERA: INDOOR_CAMERA_TRIGGERS,
    MODEL_NOC: OUTDOOR_CAMERA_TRIGGERS,
}

TRIGGER_TYPES = OUTDOOR_CAMERA_TRIGGERS + INDOOR_CAMERA_TRIGGERS

TRIGGER_SCHEMA = TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> List[dict]:
    """List device triggers for Netatmo devices."""
    registry = await entity_registry.async_get_registry(hass)
    triggers = []

    for entry in entity_registry.async_entries_for_device(registry, device_id):
        device_registry = await hass.helpers.device_registry.async_get_registry()
        device = device_registry.async_get(device_id)

        if entry.domain == "camera" and device.model == "Smart Outdoor Camera":
            for trigger in OUTDOOR_CAMERA_TRIGGERS:
                triggers.append(
                    {
                        CONF_PLATFORM: "device",
                        CONF_DEVICE_ID: device_id,
                        CONF_DOMAIN: DOMAIN,
                        CONF_ENTITY_ID: entry.entity_id,
                        CONF_TYPE: trigger,
                    }
                )

        if entry.domain == "camera" and device.model == "Smart Indoor Camera":
            for trigger in INDOOR_CAMERA_TRIGGERS:
                triggers.append(
                    {
                        CONF_PLATFORM: "device",
                        CONF_DEVICE_ID: device_id,
                        CONF_DOMAIN: DOMAIN,
                        CONF_ENTITY_ID: entry.entity_id,
                        CONF_TYPE: trigger,
                    }
                )

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: AutomationActionType,
    automation_info: dict,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    config = TRIGGER_SCHEMA(config)

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get(config[CONF_DEVICE_ID])

    event_config = {
        event_trigger.CONF_PLATFORM: "event",
        event_trigger.CONF_EVENT_TYPE: "netatmo_event",
        event_trigger.CONF_EVENT_DATA: {
            "data": {
                "event_type": config[CONF_TYPE],
                "camera_id": next(iter(device.identifiers))[-1],
            }
        },
    }

    event_config = event_trigger.TRIGGER_SCHEMA(event_config)
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, automation_info, platform_type="device"
    )
