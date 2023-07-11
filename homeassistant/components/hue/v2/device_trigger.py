"""Provides device automations for Philips Hue events."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aiohue.v2.models.button import ButtonEvent
from aiohue.v2.models.relative_rotary import (
    RelativeRotaryAction,
    RelativeRotaryDirection,
)
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

    from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo

    from ..bridge import HueBridge

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): str,
        vol.Required(CONF_SUBTYPE): vol.Union(int, str),
        vol.Optional(CONF_UNIQUE_ID): str,
    }
)

DEFAULT_BUTTON_EVENT_TYPES = (
    # all except `DOUBLE_SHORT_RELEASE`
    ButtonEvent.INITIAL_PRESS,
    ButtonEvent.REPEAT,
    ButtonEvent.SHORT_RELEASE,
    ButtonEvent.LONG_PRESS,
    ButtonEvent.LONG_RELEASE,
)

DEFAULT_ROTARY_EVENT_TYPES = (RelativeRotaryAction.START, RelativeRotaryAction.REPEAT)
DEFAULT_ROTARY_EVENT_SUBTYPES = (
    RelativeRotaryDirection.CLOCK_WISE,
    RelativeRotaryDirection.COUNTER_CLOCK_WISE,
)

DEVICE_SPECIFIC_EVENT_TYPES = {
    # device specific overrides of specific supported button events
    "Hue tap switch": (ButtonEvent.INITIAL_PRESS,),
}


async def async_validate_trigger_config(
    bridge: HueBridge,
    device_entry: DeviceEntry,
    config: ConfigType,
) -> ConfigType:
    """Validate config."""
    return TRIGGER_SCHEMA(config)


async def async_attach_trigger(
    bridge: HueBridge,
    device_entry: DeviceEntry,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
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
        hass, event_config, action, trigger_info, platform_type="device"
    )


@callback
def async_get_triggers(
    bridge: HueBridge, device_entry: DeviceEntry
) -> list[dict[str, Any]]:
    """Return device triggers for device on `v2` bridge."""
    api: HueBridgeV2 = bridge.api

    # Get Hue device id from device identifier
    hue_dev_id = get_hue_device_id(device_entry)
    # extract triggers from all button resources of this Hue device
    triggers = []
    model_id = api.devices[hue_dev_id].product_data.product_name

    for resource in api.devices.get_sensors(hue_dev_id):
        # button triggers
        if resource.type == ResourceTypes.BUTTON:
            for event_type in DEVICE_SPECIFIC_EVENT_TYPES.get(
                model_id, DEFAULT_BUTTON_EVENT_TYPES
            ):
                triggers.append(
                    {
                        CONF_DEVICE_ID: device_entry.id,
                        CONF_DOMAIN: DOMAIN,
                        CONF_PLATFORM: "device",
                        CONF_TYPE: event_type.value,
                        CONF_SUBTYPE: resource.metadata.control_id,
                        CONF_UNIQUE_ID: resource.id,
                    }
                )
        # relative_rotary triggers
        elif resource.type == ResourceTypes.RELATIVE_ROTARY:
            for event_type in DEFAULT_ROTARY_EVENT_TYPES:
                for sub_type in DEFAULT_ROTARY_EVENT_SUBTYPES:
                    triggers.append(
                        {
                            CONF_DEVICE_ID: device_entry.id,
                            CONF_DOMAIN: DOMAIN,
                            CONF_PLATFORM: "device",
                            CONF_TYPE: event_type.value,
                            CONF_SUBTYPE: sub_type.value,
                            CONF_UNIQUE_ID: resource.id,
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
