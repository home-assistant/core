"""Provides device automations for RFXCOM RFXtrx."""

import RFXtrx as rfxtrxmod
import voluptuous as vol

from homeassistant.components.device_automation import (
    DEVICE_TRIGGER_BASE_SCHEMA,
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from . import DOMAIN
from .const import EVENT_RFXTRX_EVENT
from .helpers import async_get_device_object

CONF_SUBTYPE = "subtype"

CONF_TYPE_COMMAND = "command"
CONF_TYPE_STATUS = "status"

TRIGGER_SELECTION = {
    CONF_TYPE_COMMAND: "COMMANDS",
    CONF_TYPE_STATUS: "STATUS",
}
TRIGGER_TYPES = [
    CONF_TYPE_COMMAND,
    CONF_TYPE_STATUS,
]
TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
        vol.Required(CONF_SUBTYPE): str,
    }
)

# Legacy X10 security tamper status subtypes from pyRFXtrx < 0.32.0,
# mapped to their replacement base sensor status. With pyRFXtrx 0.32.0+
# the tamper bit is reported as a separate ``Tamper`` boolean field on
# Security1 events.
LEGACY_STATUS_TAMPER_SUBTYPES = {
    "Normal Tamper": "Normal",
    "Normal Delayed Tamper": "Normal Delayed",
    "Alarm Tamper": "Alarm",
    "Alarm Delayed Tamper": "Alarm Delayed",
    "Motion Tamper": "Motion",
    "No Motion Tamper": "No Motion",
}


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device triggers for RFXCOM RFXtrx devices."""
    device = async_get_device_object(hass, device_id)

    return [
        {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: conf_type,
            CONF_SUBTYPE: command,
        }
        for conf_type in TRIGGER_TYPES
        for command in getattr(device, TRIGGER_SELECTION[conf_type], {}).values()
    ]


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    config = TRIGGER_SCHEMA(config)

    device = async_get_device_object(hass, config[CONF_DEVICE_ID])

    action_type = config[CONF_TYPE]
    sub_type = config[CONF_SUBTYPE]
    commands = getattr(device, TRIGGER_SELECTION[action_type], {})
    valid_subtypes = commands.values()
    # Accept legacy ``*_Tamper`` subtypes saved from pyRFXtrx < 0.32.0 as
    # long as the device is a Security1 device that still supports the
    # corresponding base subtype. Tamper was only ever a Security1 concept.
    base_sub_type = (
        LEGACY_STATUS_TAMPER_SUBTYPES.get(sub_type)
        if action_type == CONF_TYPE_STATUS
        and isinstance(device, rfxtrxmod.SecurityDevice)
        else None
    )
    if sub_type not in valid_subtypes and base_sub_type not in valid_subtypes:
        raise InvalidDeviceAutomationConfig(
            f"Subtype {sub_type} not found in device triggers {commands}"
        )

    return config


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    config = TRIGGER_SCHEMA(config)

    event_data = {ATTR_DEVICE_ID: config[CONF_DEVICE_ID]}
    sub_type = config[CONF_SUBTYPE]

    if config[CONF_TYPE] == CONF_TYPE_COMMAND:
        event_data["values"] = {"Command": sub_type}
    elif config[CONF_TYPE] == CONF_TYPE_STATUS:
        # Tamper was only ever a Security1 concept. For Security1 devices,
        # discriminate on the ``Tamper`` boolean introduced in pyRFXtrx
        # 0.32.0 so that legacy automations using ``Motion`` and
        # ``Motion Tamper`` (etc.) keep firing on disjoint event sets,
        # matching the pre-0.32.0 behaviour.
        device = async_get_device_object(hass, config[CONF_DEVICE_ID])
        if isinstance(device, rfxtrxmod.SecurityDevice):
            base_sub_type = LEGACY_STATUS_TAMPER_SUBTYPES.get(sub_type)
            event_data["values"] = {
                "Sensor Status": base_sub_type or sub_type,
                "Tamper": base_sub_type is not None,
            }
        else:
            event_data["values"] = {"Sensor Status": sub_type}

    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: EVENT_RFXTRX_EVENT,
            event_trigger.CONF_EVENT_DATA: event_data,
        }
    )

    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )
