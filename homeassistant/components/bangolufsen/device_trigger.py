"""Device triggers for the Bang & Olufsen integration."""
from __future__ import annotations

from typing import Any

from mozart_api.mozart_client import MozartClient
import voluptuous as vol

from homeassistant.components.automation import TriggerActionType, TriggerInfo
from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_HOST,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import BANGOLUFSEN_EVENT, DOMAIN, EntityEnum
from .media_player import BangOlufsenMediaPlayer

BUTTON_TRIGGERS = (
    "Preset1_shortPress",
    "Preset2_shortPress",
    "Preset3_shortPress",
    "Preset4_shortPress",
    "PlayPause_shortPress",
    "PlayPause_longPress",
    "Next_shortPress",
    "Previous_shortPress",
    "Microphone_shortPress",
    "Bluetooth_shortPress",
    "Bluetooth_longPress",
)

REMOTE_TRIGGERS = (
    "Control/Wind_KeyPress",
    "Control/Rewind_KeyPress",
    "Control/Play_KeyPress",
    "Control/Stop_KeyPress",
    "Control/Red_KeyPress",
    "Control/Green_KeyPress",
    "Control/Yellow_KeyPress",
    "Control/Blue_KeyPress",
    "Control/Up_KeyPress",
    "Control/Down_KeyPress",
    "Control/Left_KeyPress",
    "Control/Right_KeyPress",
    "Control/Select_KeyPress",
    "Control/Digit0_KeyPress",
    "Control/Digit1_KeyPress",
    "Control/Digit2_KeyPress",
    "Control/Digit3_KeyPress",
    "Control/Digit4_KeyPress",
    "Control/Digit5_KeyPress",
    "Control/Digit6_KeyPress",
    "Control/Digit7_KeyPress",
    "Control/Digit8_KeyPress",
    "Control/Digit9_KeyPress",
    "Light/Wind_KeyPress",
    "Light/Rewind_KeyPress",
    "Light/Play_KeyPress",
    "Light/Stop_KeyPress",
    "Light/Red_KeyPress",
    "Light/Green_KeyPress",
    "Light/Yellow_KeyPress",
    "Light/Blue_KeyPress",
    "Light/Up_KeyPress",
    "Light/Down_KeyPress",
    "Light/Left_KeyPress",
    "Light/Right_KeyPress",
    "Light/Select_KeyPress",
    "Light/Digit0_KeyPress",
    "Light/Digit1_KeyPress",
    "Light/Digit2_KeyPress",
    "Light/Digit3_KeyPress",
    "Light/Digit4_KeyPress",
    "Light/Digit5_KeyPress",
    "Light/Digit6_KeyPress",
    "Light/Digit7_KeyPress",
    "Light/Digit8_KeyPress",
    "Light/Digit9_KeyPress",
    "Control/Wind_KeyRelease",
    "Control/Rewind_KeyRelease",
    "Control/Play_KeyRelease",
    "Control/Stop_KeyRelease",
    "Control/Red_KeyRelease",
    "Control/Green_KeyRelease",
    "Control/Yellow_KeyRelease",
    "Control/Blue_KeyRelease",
    "Control/Up_KeyRelease",
    "Control/Down_KeyRelease",
    "Control/Left_KeyRelease",
    "Control/Right_KeyRelease",
    "Control/Select_KeyRelease",
    "Control/Digit0_KeyRelease",
    "Control/Digit1_KeyRelease",
    "Control/Digit2_KeyRelease",
    "Control/Digit3_KeyRelease",
    "Control/Digit4_KeyRelease",
    "Control/Digit5_KeyRelease",
    "Control/Digit6_KeyRelease",
    "Control/Digit7_KeyRelease",
    "Control/Digit8_KeyRelease",
    "Control/Digit9_KeyRelease",
    "Light/Wind_KeyRelease",
    "Light/Rewind_KeyRelease",
    "Light/Play_KeyRelease",
    "Light/Stop_KeyRelease",
    "Light/Red_KeyRelease",
    "Light/Green_KeyRelease",
    "Light/Yellow_KeyRelease",
    "Light/Blue_KeyRelease",
    "Light/Up_KeyRelease",
    "Light/Down_KeyRelease",
    "Light/Left_KeyRelease",
    "Light/Right_KeyRelease",
    "Light/Select_KeyRelease",
    "Light/Digit0_KeyRelease",
    "Light/Digit1_KeyRelease",
    "Light/Digit2_KeyRelease",
    "Light/Digit3_KeyRelease",
    "Light/Digit4_KeyRelease",
    "Light/Digit5_KeyRelease",
    "Light/Digit6_KeyRelease",
    "Light/Digit7_KeyRelease",
    "Light/Digit8_KeyRelease",
    "Light/Digit9_KeyRelease",
)

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(REMOTE_TRIGGERS + BUTTON_TRIGGERS),
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List device triggers for Bang & Olufsen devices."""
    triggers = []

    # Get the host IP address
    device_registry = dr.async_get(hass)
    serial_number = list(device_registry.devices[device_id].identifiers)[0][1]
    media_player: BangOlufsenMediaPlayer = hass.data[DOMAIN][serial_number][
        EntityEnum.MEDIA_PLAYER
    ]

    client = MozartClient(host=media_player.entry.data[CONF_HOST])

    # Get if a remote control is connected
    bluetooth_remote_list = client.get_bluetooth_remotes(async_req=True).get()
    remote_control_available = bool(len(bluetooth_remote_list.items))

    trigger_types: list[str] = list(BUTTON_TRIGGERS)

    if remote_control_available:
        trigger_types.extend(REMOTE_TRIGGERS)

    for trigger_type in trigger_types:
        triggers.append(
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_TYPE: trigger_type,
            }
        )
    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    automation_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""

    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: BANGOLUFSEN_EVENT,
            event_trigger.CONF_EVENT_DATA: {
                CONF_TYPE: config[CONF_TYPE],
                CONF_DEVICE_ID: config[CONF_DEVICE_ID],
            },
        }
    )

    return await event_trigger.async_attach_trigger(
        hass, event_config, action, automation_info, platform_type="device"
    )
