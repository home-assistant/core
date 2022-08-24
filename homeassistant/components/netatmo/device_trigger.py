"""Provides device automations for Netatmo."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry,
)
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .climate import STATE_NETATMO_AWAY, STATE_NETATMO_HG, STATE_NETATMO_SCHEDULE
from .const import (
    CLIMATE_TRIGGERS,
    DOMAIN,
    EVENT_TYPE_THERM_MODE,
    INDOOR_CAMERA_TRIGGERS,
    MODEL_NACAMERA,
    MODEL_NATHERM1,
    MODEL_NOC,
    MODEL_NRV,
    NETATMO_EVENT,
    OUTDOOR_CAMERA_TRIGGERS,
)

CONF_SUBTYPE = "subtype"

DEVICES = {
    MODEL_NACAMERA: INDOOR_CAMERA_TRIGGERS,
    MODEL_NOC: OUTDOOR_CAMERA_TRIGGERS,
    MODEL_NATHERM1: CLIMATE_TRIGGERS,
    MODEL_NRV: CLIMATE_TRIGGERS,
}

SUBTYPES = {
    EVENT_TYPE_THERM_MODE: [
        STATE_NETATMO_SCHEDULE,
        STATE_NETATMO_HG,
        STATE_NETATMO_AWAY,
    ]
}

TRIGGER_TYPES = OUTDOOR_CAMERA_TRIGGERS + INDOOR_CAMERA_TRIGGERS + CLIMATE_TRIGGERS

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
        vol.Optional(CONF_SUBTYPE): str,
    }
)


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    config = TRIGGER_SCHEMA(config)

    device_registry = dr.async_get(hass)
    device = device_registry.async_get(config[CONF_DEVICE_ID])

    if not device:
        raise InvalidDeviceAutomationConfig(
            f"Trigger invalid, device with ID {config[CONF_DEVICE_ID]} not found"
        )

    trigger = config[CONF_TYPE]

    if (
        not device
        or device.model not in DEVICES
        or trigger not in DEVICES[device.model]
    ):
        raise InvalidDeviceAutomationConfig(f"Unsupported model {device.model}")

    return config


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device triggers for Netatmo devices."""
    registry = entity_registry.async_get(hass)
    device_registry = dr.async_get(hass)
    triggers = []

    for entry in entity_registry.async_entries_for_device(registry, device_id):
        if (
            device := device_registry.async_get(device_id)
        ) is None or device.model is None:
            continue

        for trigger in DEVICES.get(device.model, []):
            if trigger in SUBTYPES:
                for subtype in SUBTYPES[trigger]:
                    triggers.append(
                        {
                            CONF_PLATFORM: "device",
                            CONF_DEVICE_ID: device_id,
                            CONF_DOMAIN: DOMAIN,
                            CONF_ENTITY_ID: entry.entity_id,
                            CONF_TYPE: trigger,
                            CONF_SUBTYPE: subtype,
                        }
                    )
            else:
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
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(config[CONF_DEVICE_ID])

    if not device:
        return lambda: None

    if device.model not in DEVICES:
        return lambda: None

    event_config = {
        event_trigger.CONF_PLATFORM: "event",
        event_trigger.CONF_EVENT_TYPE: NETATMO_EVENT,
        event_trigger.CONF_EVENT_DATA: {
            "type": config[CONF_TYPE],
            ATTR_DEVICE_ID: config[ATTR_DEVICE_ID],
        },
    }

    if config[CONF_TYPE] in SUBTYPES:
        event_config.update(
            {event_trigger.CONF_EVENT_DATA: {"data": {"mode": config[CONF_SUBTYPE]}}}
        )

    event_config = event_trigger.TRIGGER_SCHEMA(event_config)
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )
