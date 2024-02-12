"""Provides device triggers for Xiaomi BLE."""
from __future__ import annotations

from dataclasses import dataclass
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
    BUTTON,
    BUTTON_PRESS,
    BUTTON_PRESS_DOUBLE_LONG,
    BUTTON_PRESS_LONG,
    CONF_SUBTYPE,
    CUBE,
    DIMMER,
    DOMAIN,
    DOUBLE_BUTTON,
    DOUBLE_BUTTON_PRESS_DOUBLE_LONG,
    EVENT_CLASS,
    EVENT_CLASS_BUTTON,
    EVENT_CLASS_CUBE,
    EVENT_CLASS_DIMMER,
    EVENT_CLASS_MOTION,
    EVENT_TYPE,
    MOTION,
    MOTION_DEVICE,
    REMOTE,
    REMOTE_BATHROOM,
    REMOTE_FAN,
    REMOTE_VENFAN,
    TRIPPLE_BUTTON,
    TRIPPLE_BUTTON_PRESS_DOUBLE_LONG,
    XIAOMI_BLE_EVENT,
)

TRIGGERS_BY_TYPE = {
    BUTTON_PRESS: ["press"],
    BUTTON_PRESS_LONG: ["press", "long_press"],
    BUTTON_PRESS_DOUBLE_LONG: ["press", "double_press", "long_press"],
    CUBE: ["rotate_left", "rotate_right"],
    DIMMER: [
        "press",
        "long_press",
        "rotate_left",
        "rotate_right",
        "rotate_left_pressed",
        "rotate_right_pressed",
    ],
    MOTION_DEVICE: ["motion_detected"],
}

EVENT_TYPES = {
    BUTTON: ["button"],
    CUBE: ["cube"],
    DIMMER: ["dimmer"],
    DOUBLE_BUTTON: ["button_left", "button_right"],
    TRIPPLE_BUTTON: ["button_left", "button_middle", "button_right"],
    REMOTE: [
        "button_on",
        "button_off",
        "button_brightness",
        "button_plus",
        "button_min",
        "button_m",
    ],
    REMOTE_BATHROOM: [
        "button_heat",
        "button_air_exchange",
        "button_dry",
        "button_fan",
        "button_swing",
        "button_decrease_speed",
        "button_increase_speed",
        "button_stop",
        "button_light",
    ],
    REMOTE_FAN: [
        "button_fan",
        "button_light",
        "button_wind_speed",
        "button_wind_mode",
        "button_brightness",
        "button_color_temperature",
    ],
    REMOTE_VENFAN: [
        "button_swing",
        "button_power",
        "button_timer_30_minutes",
        "button_timer_60_minutes",
        "button_increase_wind_speed",
        "button_decrease_wind_speed",
    ],
    MOTION: ["motion"],
}


@dataclass
class TriggerModelData:
    """Data class for trigger model data."""

    event_class: str
    event_types: list[str]
    triggers: list[str]


TRIGGER_MODEL_DATA = {
    BUTTON_PRESS: TriggerModelData(
        event_class=EVENT_CLASS_BUTTON,
        event_types=EVENT_TYPES[BUTTON],
        triggers=TRIGGERS_BY_TYPE[BUTTON_PRESS],
    ),
    BUTTON_PRESS_DOUBLE_LONG: TriggerModelData(
        event_class=EVENT_CLASS_BUTTON,
        event_types=EVENT_TYPES[BUTTON],
        triggers=TRIGGERS_BY_TYPE[BUTTON_PRESS_DOUBLE_LONG],
    ),
    DOUBLE_BUTTON_PRESS_DOUBLE_LONG: TriggerModelData(
        event_class=EVENT_CLASS_BUTTON,
        event_types=EVENT_TYPES[DOUBLE_BUTTON],
        triggers=TRIGGERS_BY_TYPE[BUTTON_PRESS_DOUBLE_LONG],
    ),
    CUBE: TriggerModelData(
        event_class=EVENT_CLASS_CUBE,
        event_types=EVENT_TYPES[CUBE],
        triggers=TRIGGERS_BY_TYPE[CUBE],
    ),
    DIMMER: TriggerModelData(
        event_class=EVENT_CLASS_DIMMER,
        event_types=EVENT_TYPES[DIMMER],
        triggers=TRIGGERS_BY_TYPE[DIMMER],
    ),
    TRIPPLE_BUTTON_PRESS_DOUBLE_LONG: TriggerModelData(
        event_class=EVENT_CLASS_BUTTON,
        event_types=EVENT_TYPES[TRIPPLE_BUTTON],
        triggers=TRIGGERS_BY_TYPE[BUTTON_PRESS_DOUBLE_LONG],
    ),
    REMOTE: TriggerModelData(
        event_class=EVENT_CLASS_BUTTON,
        event_types=EVENT_TYPES[REMOTE],
        triggers=TRIGGERS_BY_TYPE[BUTTON_PRESS_LONG],
    ),
    REMOTE_BATHROOM: TriggerModelData(
        event_class=EVENT_CLASS_BUTTON,
        event_types=EVENT_TYPES[REMOTE_BATHROOM],
        triggers=TRIGGERS_BY_TYPE[BUTTON_PRESS_LONG],
    ),
    REMOTE_FAN: TriggerModelData(
        event_class=EVENT_CLASS_BUTTON,
        event_types=EVENT_TYPES[REMOTE_FAN],
        triggers=TRIGGERS_BY_TYPE[BUTTON_PRESS_LONG],
    ),
    REMOTE_VENFAN: TriggerModelData(
        event_class=EVENT_CLASS_BUTTON,
        event_types=EVENT_TYPES[REMOTE_VENFAN],
        triggers=TRIGGERS_BY_TYPE[BUTTON_PRESS_LONG],
    ),
    MOTION_DEVICE: TriggerModelData(
        event_class=EVENT_CLASS_MOTION,
        event_types=EVENT_TYPES[MOTION],
        triggers=TRIGGERS_BY_TYPE[MOTION_DEVICE],
    ),
}


MODEL_DATA = {
    "JTYJGD03MI": TRIGGER_MODEL_DATA[BUTTON_PRESS],
    "MS1BB(MI)": TRIGGER_MODEL_DATA[BUTTON_PRESS],
    "RTCGQ02LM": TRIGGER_MODEL_DATA[BUTTON_PRESS],
    "SJWS01LM": TRIGGER_MODEL_DATA[BUTTON_PRESS],
    "K9BB-1BTN": TRIGGER_MODEL_DATA[BUTTON_PRESS_DOUBLE_LONG],
    "YLAI003": TRIGGER_MODEL_DATA[BUTTON_PRESS_DOUBLE_LONG],
    "XMWXKG01LM": TRIGGER_MODEL_DATA[BUTTON_PRESS_DOUBLE_LONG],
    "K9B-1BTN": TRIGGER_MODEL_DATA[BUTTON_PRESS_DOUBLE_LONG],
    "XMWXKG01YL": TRIGGER_MODEL_DATA[DOUBLE_BUTTON_PRESS_DOUBLE_LONG],
    "K9B-2BTN": TRIGGER_MODEL_DATA[DOUBLE_BUTTON_PRESS_DOUBLE_LONG],
    "K9B-3BTN": TRIGGER_MODEL_DATA[TRIPPLE_BUTTON_PRESS_DOUBLE_LONG],
    "YLYK01YL": TRIGGER_MODEL_DATA[REMOTE],
    "YLYK01YL-FANRC": TRIGGER_MODEL_DATA[REMOTE_FAN],
    "YLYK01YL-VENFAN": TRIGGER_MODEL_DATA[REMOTE_VENFAN],
    "YLYK01YL-BHFRC": TRIGGER_MODEL_DATA[REMOTE_BATHROOM],
    "MUE4094RT": TRIGGER_MODEL_DATA[MOTION_DEVICE],
    "XMMF01JQD": TRIGGER_MODEL_DATA[CUBE],
    "YLKG07YL/YLKG08YL": TRIGGER_MODEL_DATA[DIMMER],
}


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate trigger config."""
    device_id = config[CONF_DEVICE_ID]
    if model_data := _async_trigger_model_data(hass, device_id):
        schema = DEVICE_TRIGGER_BASE_SCHEMA.extend(
            {
                vol.Required(CONF_TYPE): vol.In(model_data.event_types),
                vol.Required(CONF_SUBTYPE): vol.In(model_data.triggers),
            }
        )
        return schema(config)  # type: ignore[no-any-return]
    return config


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List a list of triggers for Xiaomi BLE devices."""

    # Check if device is a model supporting device triggers.
    if not (model_data := _async_trigger_model_data(hass, device_id)):
        return []

    event_types = model_data.event_types
    event_subtypes = model_data.triggers
    return [
        {
            # Required fields of TRIGGER_BASE_SCHEMA
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            # Required fields of TRIGGER_SCHEMA
            CONF_TYPE: event_type,
            CONF_SUBTYPE: event_subtype,
        }
        for event_type in event_types
        for event_subtype in event_subtypes
    ]


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    return await event_trigger.async_attach_trigger(
        hass,
        event_trigger.TRIGGER_SCHEMA(
            {
                event_trigger.CONF_PLATFORM: CONF_EVENT,
                event_trigger.CONF_EVENT_TYPE: XIAOMI_BLE_EVENT,
                event_trigger.CONF_EVENT_DATA: {
                    CONF_DEVICE_ID: config[CONF_DEVICE_ID],
                    EVENT_CLASS: config[CONF_TYPE],
                    EVENT_TYPE: config[CONF_SUBTYPE],
                },
            }
        ),
        action,
        trigger_info,
        platform_type="device",
    )


def _async_trigger_model_data(
    hass: HomeAssistant, device_id: str
) -> TriggerModelData | None:
    """Get available triggers for a given model."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    if device and device.model and (model_data := MODEL_DATA.get(device.model)):
        return model_data
    return None
