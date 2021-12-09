"""Provides device automations for Philips Hue events."""
from __future__ import annotations

from typing import TYPE_CHECKING

from aiohue.v2.models.button import ButtonEvent
from aiohue.v2.models.resource import ResourceTypes
import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_PLATFORM,
    CONF_TYPE,
    CONF_UNIQUE_ID,
)
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.typing import ConfigType

from ..const import ATTR_HUE_EVENT, CONF_SUBTYPE, DOMAIN

if TYPE_CHECKING:
    from aiohue.v2 import HueBridgeV2

    from homeassistant.components.automation import (
        AutomationActionType,
        AutomationTriggerInfo,
    )

    from ..bridge import HueBridge

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): str,
        vol.Required(CONF_SUBTYPE): int,
        vol.Optional(CONF_UNIQUE_ID): str,
    }
)


async def async_validate_trigger_config(
    bridge: "HueBridge",
    device_entry: DeviceEntry,
    config: ConfigType,
):
    """Validate config."""
    config = TRIGGER_SCHEMA(config)
    return config


async def async_attach_trigger(
    bridge: "HueBridge",
    device_entry: DeviceEntry,
    config: ConfigType,
    action: "AutomationActionType",
    automation_info: "AutomationTriggerInfo",
) -> CALLBACK_TYPE:
    """Listen for state changes based on configuration."""
    hass = bridge.hass
    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: ATTR_HUE_EVENT,
            event_trigger.CONF_EVENT_DATA: {
                CONF_DEVICE_ID: config[CONF_DEVICE_ID],
                CONF_TYPE: config[CONF_TYPE],
                CONF_SUBTYPE: config[CONF_SUBTYPE],
            },
        }
    )
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, automation_info, platform_type="device"
    )


async def async_get_triggers(bridge: "HueBridge", device_entry: DeviceEntry):
    """Return device triggers for device on `v2` bridge."""
    api: HueBridgeV2 = bridge.api

    # Get Hue device id from device identifier
    hue_dev_id = get_hue_device_id(device_entry)
    # extract triggers from all button resources of this Hue device
    triggers = []
    for resource in api.devices.get_sensors(hue_dev_id):
        if resource.type != ResourceTypes.BUTTON:
            continue
        for event_type in (x.value for x in ButtonEvent if x != ButtonEvent.UNKNOWN):
            triggers.append(
                {
                    CONF_DEVICE_ID: device_entry.id,
                    CONF_DOMAIN: DOMAIN,
                    CONF_PLATFORM: "device",
                    CONF_TYPE: event_type,
                    CONF_SUBTYPE: resource.metadata.control_id,
                    CONF_UNIQUE_ID: device_entry.id,
                }
            )
    return triggers


@callback
def get_hue_device_id(device_entry: DeviceEntry) -> str | None:
    """Get Hue device id from device entry."""
    return next(
        (
            identifier[1]
            for identifier in device_entry.identifiers
            if identifier[0] == DOMAIN
            and ":" not in identifier[1]  # filter out v1 mac id
        ),
        None,
    )
