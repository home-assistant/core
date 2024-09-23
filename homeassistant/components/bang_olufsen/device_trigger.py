"""Device triggers for the Bang & Olufsen integration."""

from __future__ import annotations

from typing import Any, cast

from mozart_api.models import PairedRemote
from mozart_api.mozart_client import MozartClient
import voluptuous as vol

from homeassistant.components.automation import TriggerActionType, TriggerInfo
from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    CONF_DEVICE,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_EVENT,
    CONF_PLATFORM,
    CONF_TYPE,
    Platform,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .const import BANG_OLUFSEN_EVENT, DOMAIN

DEFAULT_TRIGGERS = (
    "Bluetooth_longPress",
    "Bluetooth_shortPress",
    "Microphone_shortPress",
    "Next_shortPress",
    "PlayPause_longPress",
    "PlayPause_shortPress",
    "Preset1_shortPress",
    "Preset2_shortPress",
    "Preset3_shortPress",
    "Preset4_shortPress",
    "Previous_shortPress",
)

REMOTE_TRIGGERS = (
    "Control/Blue_KeyPress",
    "Control/Blue_KeyRelease",
    "Control/Digit0_KeyPress",
    "Control/Digit0_KeyRelease",
    "Control/Digit1_KeyPress",
    "Control/Digit1_KeyRelease",
    "Control/Digit2_KeyPress",
    "Control/Digit2_KeyRelease",
    "Control/Digit3_KeyPress",
    "Control/Digit3_KeyRelease",
    "Control/Digit4_KeyPress",
    "Control/Digit4_KeyRelease",
    "Control/Digit5_KeyPress",
    "Control/Digit5_KeyRelease",
    "Control/Digit6_KeyPress",
    "Control/Digit6_KeyRelease",
    "Control/Digit7_KeyPress",
    "Control/Digit7_KeyRelease",
    "Control/Digit8_KeyPress",
    "Control/Digit8_KeyRelease",
    "Control/Digit9_KeyPress",
    "Control/Digit9_KeyRelease",
    "Control/Down_KeyPress",
    "Control/Down_KeyRelease",
    "Control/Func1_KeyPress",
    "Control/Func1_KeyRelease",
    "Control/Func11_KeyPress",
    "Control/Func11_KeyRelease",
    "Control/Func16_KeyPress",
    "Control/Func16_KeyRelease",
    "Control/Func6_KeyPress",
    "Control/Func6_KeyRelease",
    "Control/Green_KeyPress",
    "Control/Green_KeyRelease",
    "Control/Left_KeyPress",
    "Control/Left_KeyRelease",
    "Control/Play_KeyPress",
    "Control/Play_KeyRelease",
    "Control/Red_KeyPress",
    "Control/Red_KeyRelease",
    "Control/Rewind_KeyPress",
    "Control/Rewind_KeyRelease",
    "Control/Right_KeyPress",
    "Control/Right_KeyRelease",
    "Control/Select_KeyPress",
    "Control/Select_KeyRelease",
    "Control/Stop_KeyPress",
    "Control/Stop_KeyRelease",
    "Control/Up_KeyPress",
    "Control/Up_KeyRelease",
    "Control/Wind_KeyPress",
    "Control/Wind_KeyRelease",
    "Control/Yellow_KeyPress",
    "Control/Yellow_KeyRelease",
    "Light/Blue_KeyPress",
    "Light/Blue_KeyRelease",
    "Light/Digit0_KeyPress",
    "Light/Digit0_KeyRelease",
    "Light/Digit1_KeyPress",
    "Light/Digit1_KeyRelease",
    "Light/Digit2_KeyPress",
    "Light/Digit2_KeyRelease",
    "Light/Digit3_KeyPress",
    "Light/Digit3_KeyRelease",
    "Light/Digit4_KeyPress",
    "Light/Digit4_KeyRelease",
    "Light/Digit5_KeyPress",
    "Light/Digit5_KeyRelease",
    "Light/Digit6_KeyPress",
    "Light/Digit6_KeyRelease",
    "Light/Digit7_KeyPress",
    "Light/Digit7_KeyRelease",
    "Light/Digit8_KeyPress",
    "Light/Digit8_KeyRelease",
    "Light/Digit9_KeyPress",
    "Light/Digit9_KeyRelease",
    "Light/Down_KeyPress",
    "Light/Down_KeyRelease",
    "Light/Func1_KeyPress",
    "Light/Func1_KeyRelease",
    "Light/Func11_KeyPress",
    "Light/Func11_KeyRelease",
    "Light/Func12_KeyPress",
    "Light/Func12_KeyRelease",
    "Light/Func13_KeyPress",
    "Light/Func13_KeyRelease",
    "Light/Func14_KeyPress",
    "Light/Func14_KeyRelease",
    "Light/Func15_KeyPress",
    "Light/Func15_KeyRelease",
    "Light/Func16_KeyPress",
    "Light/Func16_KeyRelease",
    "Light/Func17_KeyPress",
    "Light/Func17_KeyRelease",
    "Light/Green_KeyPress",
    "Light/Green_KeyRelease",
    "Light/Left_KeyPress",
    "Light/Left_KeyRelease",
    "Light/Play_KeyPress",
    "Light/Play_KeyRelease",
    "Light/Red_KeyPress",
    "Light/Red_KeyRelease",
    "Light/Rewind_KeyPress",
    "Light/Rewind_KeyRelease",
    "Light/Right_KeyPress",
    "Light/Right_KeyRelease",
    "Light/Select_KeyPress",
    "Light/Select_KeyRelease",
    "Light/Stop_KeyPress",
    "Light/Stop_KeyRelease",
    "Light/Up_KeyPress",
    "Light/Up_KeyRelease",
    "Light/Wind_KeyPress",
    "Light/Wind_KeyRelease",
    "Light/Yellow_KeyPress",
    "Light/Yellow_KeyRelease",
)

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(REMOTE_TRIGGERS + DEFAULT_TRIGGERS),
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List device triggers for Bang & Olufsen devices."""
    # Check if a Beoremote One is connected to the device and remote triggers should be added

    # Get the serial number
    device_registry = dr.async_get(hass)
    serial_number = list(device_registry.devices[device_id].identifiers)[0][1]

    # Get the entity id
    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        Platform.MEDIA_PLAYER, DOMAIN, serial_number
    )
    assert entity_id

    entry = entity_registry.async_get(entity_id)
    assert entry

    client: MozartClient = hass.data[DOMAIN][entry.config_entry_id].client

    # Get if a remote control is connected
    bluetooth_remote_list = await client.get_bluetooth_remotes()
    remote_control_available = bool(
        len(cast(list[PairedRemote], bluetooth_remote_list.items))
    )

    # Always add default triggers
    trigger_types: list[str] = list(DEFAULT_TRIGGERS)

    if remote_control_available:
        trigger_types.extend(REMOTE_TRIGGERS)

    return [
        {
            CONF_PLATFORM: CONF_DEVICE,
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: trigger_type,
        }
        for trigger_type in trigger_types
    ]


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    automation_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""

    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: CONF_EVENT,
            event_trigger.CONF_EVENT_TYPE: BANG_OLUFSEN_EVENT,
            event_trigger.CONF_EVENT_DATA: {
                CONF_TYPE: config[CONF_TYPE],
                CONF_DEVICE_ID: config[CONF_DEVICE_ID],
            },
        }
    )

    return await event_trigger.async_attach_trigger(
        hass, event_config, action, automation_info, platform_type=CONF_DEVICE
    )
