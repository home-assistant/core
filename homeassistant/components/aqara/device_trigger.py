"""Provides device triggers for Aqara."""
from __future__ import annotations
from typing import Any
import voluptuous as vol
from homeassistant.components.automation import (
    AutomationActionType,
    AutomationTriggerInfo,
)

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_PLATFORM,
    CONF_TYPE,
)

from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import ConfigType

from . import DOMAIN

CONF_SUBTYPE = "subtype"

# event of aqara cube
EVENT_FLIP_90 = "Flip 90°"
EVENT_FLIP_180 = "Flip 180°"
EVENT_MOVE = "Push"
EVENT_TAP_TWICE = "Tap twice"
EVENT_SHAKE_AIR = "Shake"
EVENT_TRIGGER_AFTER_ONE_MINUTE = "Triggered after one-minute inactivity"
EVENT_TRIGGER_ROTATE = "Rotate"


# 动静贴
AQARA_EVENTS_MAP = {
    # vibration
    "lumi.vibration.aq1": {
        "13.1.85": {
            "1": "Vibration is detected",
            "2": "Tilt is detected",
            "3": "Drop is detected",
        }
    },
    "lumi.vibration.agl01": {
        "13.1.85": {"1": "Percussion"},
        "13.7.85": {"1": "is moved"},
    },
    # single switch
    "lumi.remote.acn007": {
        "13.1.85": {"1": "click", "2": "double_click", "3": "long_click_press"}
    },
    "lumi.remote.b1acn02": {
        "13.1.85": {"1": "click", "2": "double_click", "3": "long_click_press"}
    },
    "lumi.remote.b186acn03": {
        "13.1.85": {"1": "click", "2": "double_click", "3": "long_click_press"}
    },
    "lumi.sensor_switch.v1": {
        "13.1.85": {"1": "click", "2": "double_click", "3": "long_click_press"}
    },
    "lumi.sensor_switch.v2": {
        "13.1.85": {"1": "click", "2": "double_click", "3": "long_click_press"}
    },
    "lumi.sensor_switch.aq2": {
        "13.1.85": {"1": "click", "2": "double_click", "3": "long_click_press"}
    },
    "lumi.sensor_switch.aq3": {
        "13.1.85": {"1": "click", "2": "double_click", "3": "long_click_press"}
    },
    "lumi.sensor_switch.es2": {
        "13.1.85": {"1": "click", "2": "double_click", "3": "long_click_press"}
    },
    "lumi.sensor_switch.es3": {
        "13.1.85": {"1": "click", "2": "double_click", "3": "long_click_press"}
    },
    "lumi.sensor_86sw1.v1": {
        "13.1.85": {"1": "click", "2": "double_click", "3": "long_click_press"}
    },
    "lumi.remote.b1acn01": {
        "13.1.85": {"1": "click", "2": "double_click", "3": "long_click_press"}
    },
    "lumi.remote.acn001": {
        "13.1.85": {"1": "click", "2": "double_click", "3": "long_click_press"}
    },
    "lumi.remote.b186acn02": {
        "13.1.85": {"1": "click", "2": "double_click", "3": "long_click_press"}
    },
    "lumi.remote.b18ac1": {
        "13.1.85": {"1": "click", "2": "double_click", "3": "long_click_press"}
    },
    # double switch
    "lumi.remote.b1akr1": {
        "13.1.85": {
            "1": "button1-click",
            "2": "button1-double_click",
            "3": "button1-long_click_press",
        },
        "13.2.85": {
            "1": "button2-click",
            "2": "button2-double_click",
            "3": "button2-long_click_press",
        },
    },
    "lumi.remote.acn002": {
        "13.1.85": {
            "1": "button1-click",
            "2": "button1-double_click",
            "3": "button1-long_click_press",
        },
        "13.2.85": {
            "1": "button2-click",
            "2": "button2-double_click",
            "3": "button2-long_click_press",
        },
    },
    "lumi.remote.acn004": {
        "13.1.85": {
            "1": "button1-click",
            "2": "button1-double_click",
            "3": "button1-long_click_press",
        },
        "13.2.85": {
            "1": "button2-click",
            "2": "button2-double_click",
            "3": "button2-long_click_press",
        },
    },
    "lumi.remote.acn009": {
        "13.1.85": {
            "1": "button1-click",
            "2": "button1-double_click",
            "3": "button1-long_click_press",
        },
        "13.2.85": {
            "1": "button2-click",
            "2": "button2-double_click",
            "3": "button2-long_click_press",
        },
    },
    "lumi.switch.n2eic2": {
        "13.1.85": {
            "1": "button1-click",
            "2": "button1-double_click",
            "3": "button1-long_click_press",
        },
        "13.2.85": {
            "1": "button2-click",
            "2": "button2-double_click",
            "3": "button2-long_click_press",
        },
    },
    "lumi.switch.n1eic2": {
        "13.1.85": {
            "1": "button1-click",
            "2": "button1-double_click",
            "3": "button1-long_click_press",
        },
        "13.2.85": {
            "1": "button2-click",
            "2": "button2-double_click",
            "3": "button2-long_click_press",
        },
    },
    "lumi.remote.b286acn03": {
        "13.1.85": {
            "1": "button1-click",
            "2": "button1-double_click",
            "3": "button1-long_click_press",
        },
        "13.2.85": {
            "1": "button2-click",
            "2": "button2-double_click",
            "3": "button2-long_click_press",
        },
    },
    "lumi.sensor_86sw2.v1": {
        "13.1.85": {
            "1": "button1-click",
            "2": "button1-double_click",
            "3": "button1-long_click_press",
        },
        "13.2.85": {
            "1": "button2-click",
            "2": "button2-double_click",
            "3": "button2-long_click_press",
        },
    },
    "lumi.sensor_86sw2.es1": {
        "13.1.85": {
            "1": "button1-click",
            "2": "button1-double_click",
            "3": "button1-long_click_press",
        },
        "13.2.85": {
            "1": "button2-click",
            "2": "button2-double_click",
            "3": "button2-long_click_press",
        },
    },
    "lumi.remote.b28ac1": {
        "13.1.85": {
            "1": "button1-click",
            "2": "button1-double_click",
            "3": "button1-long_click_press",
        },
        "13.2.85": {
            "1": "button2-click",
            "2": "button2-double_click",
            "3": "button2-long_click_press",
        },
    },
    "lumi.remote.b286acn01": {
        "13.1.85": {
            "1": "button1-click",
            "2": "button1-double_click",
            "3": "button1-long_click_press",
        },
        "13.2.85": {
            "1": "button2-click",
            "2": "button2-double_click",
            "3": "button2-long_click_press",
        },
    },
    "lumi.remote.b286opcn01": {
        "13.1.85": {
            "1": "button1-click",
            "2": "button1-double_click",
            "3": "button1-long_click_press",
        },
        "13.2.85": {
            "1": "button2-click",
            "2": "button2-double_click",
            "3": "button2-long_click_press",
        },
    },
    "lumi.sensor_86sw2.aq1": {
        "13.1.85": {
            "1": "button1-click",
            "2": "button1-double_click",
            "3": "button1-long_click_press",
        },
        "13.2.85": {
            "1": "button2-click",
            "2": "button2-double_click",
            "3": "button2-long_click_press",
        },
    },
    "lumi.remote.b286acn02": {
        "13.1.85": {
            "1": "button1-click",
            "2": "button1-double_click",
            "3": "button1-long_click_press",
        },
        "13.2.85": {
            "1": "button2-click",
            "2": "button2-double_click",
            "3": "button2-long_click_press",
        },
    },
    # 旋钮开关
    "lumi.remote.rkba01": {
        "13.1.85": {"1": "Single press", "2": "Double press", "16": "Long press"}
    },
    # cube
    "lumi.sensor_cube.aqgl01": {
        "13.1.85": {
            "flip90": EVENT_FLIP_90,
            "flip180": EVENT_FLIP_180,
            "move": EVENT_MOVE,
            "tap_twice": EVENT_TAP_TWICE,
            "shake_air": EVENT_SHAKE_AIR,
            "alert": EVENT_TRIGGER_AFTER_ONE_MINUTE,
            "swing": EVENT_TRIGGER_ROTATE,
        }
    },
    "lumi.sensor_cube.es1": {
        "13.1.85": {
            "flip90": EVENT_FLIP_90,
            "flip180": EVENT_FLIP_180,
            "move": EVENT_MOVE,
            "tap_twice": EVENT_TAP_TWICE,
            "shake_air": EVENT_SHAKE_AIR,
            "alert": EVENT_TRIGGER_AFTER_ONE_MINUTE,
            "swing": EVENT_TRIGGER_ROTATE,
        }
    },
    "lumi.sensor_cube.v1": {
        "13.1.85": {
            "flip90": EVENT_FLIP_90,
            "flip180": EVENT_FLIP_180,
            "move": EVENT_MOVE,
            "tap_twice": EVENT_TAP_TWICE,
            "shake_air": EVENT_SHAKE_AIR,
            "alert": EVENT_TRIGGER_AFTER_ONE_MINUTE,
            "swing": EVENT_TRIGGER_ROTATE,
        }
    },
    "lumi.remote.cagl01": {
        "13.1.85": {
            "flip90": EVENT_FLIP_90,
            "flip180": EVENT_FLIP_180,
            "move": EVENT_MOVE,
            "tap_twice": EVENT_TAP_TWICE,
            "shake_air": EVENT_SHAKE_AIR,
            "alert": EVENT_TRIGGER_AFTER_ONE_MINUTE,
            "swing": EVENT_TRIGGER_ROTATE,
        }
    },
    "lumi.remote.cagl02": {
        "13.1.85": {
            "flip90": EVENT_FLIP_90,
            "flip180": EVENT_FLIP_180,
            "move": EVENT_MOVE,
            "tap_twice": EVENT_TAP_TWICE,
            "shake_air": EVENT_SHAKE_AIR,
            "alert": EVENT_TRIGGER_AFTER_ONE_MINUTE,
            "swing": EVENT_TRIGGER_ROTATE,
        }
    },
}


AQARA_EVENTS = {
    # CUBE
    "lumi.sensor_cube.aqgl01": (
        EVENT_FLIP_90,
        EVENT_FLIP_180,
        EVENT_MOVE,
        EVENT_TAP_TWICE,
        EVENT_SHAKE_AIR,
        EVENT_TRIGGER_AFTER_ONE_MINUTE,
        EVENT_TRIGGER_ROTATE,
    ),
    "lumi.sensor_cube.es1": (
        EVENT_FLIP_90,
        EVENT_FLIP_180,
        EVENT_MOVE,
        EVENT_TAP_TWICE,
        EVENT_SHAKE_AIR,
        EVENT_TRIGGER_AFTER_ONE_MINUTE,
        EVENT_TRIGGER_ROTATE,
    ),
    "lumi.sensor_cube.v1": (
        EVENT_FLIP_90,
        EVENT_FLIP_180,
        EVENT_MOVE,
        EVENT_TAP_TWICE,
        EVENT_SHAKE_AIR,
        EVENT_TRIGGER_AFTER_ONE_MINUTE,
        EVENT_TRIGGER_ROTATE,
    ),
    "lumi.remote.cagl01": (
        EVENT_FLIP_90,
        EVENT_FLIP_180,
        EVENT_MOVE,
        EVENT_TAP_TWICE,
        EVENT_SHAKE_AIR,
        EVENT_TRIGGER_AFTER_ONE_MINUTE,
        EVENT_TRIGGER_ROTATE,
    ),
    "lumi.remote.cagl02": (
        EVENT_FLIP_90,
        EVENT_FLIP_180,
        EVENT_MOVE,
        EVENT_TAP_TWICE,
        EVENT_SHAKE_AIR,
        EVENT_TRIGGER_AFTER_ONE_MINUTE,
        EVENT_TRIGGER_ROTATE,
    ),
    # VIBRATION
    "lumi.vibration.aq1": (
        "Vibration is detected",
        "Tilt is detected",
        "Drop is detected",
    ),
    "lumi.vibration.agl01": ("Percussion", "is moved"),
    # 旋钮开关
    "lumi.remote.rkba01": (
        "Single press",
        "Double press",
        "Long press",
        "Rotate",
        "Press and rotate",
    ),
    # wireless SWITCH
    # 'lumi.switch.rkna01':('Turn on','Turn off','Long press','Rotate','Press and rotate'),#智能旋钮开关 H1（零火版）
    "lumi.remote.acn007": ("click", "double_click", "long_click_press"),
    "lumi.remote.b1acn02": ("click", "double_click", "long_click_press"),
    "lumi.remote.b186acn03": ("click", "double_click", "long_click_press"),
    "lumi.remote.b186acn02": ("click", "double_click", "long_click_press"),
    "lumi.sensor_switch.v1": ("click", "double_click", "long_click_press"),
    "lumi.sensor_switch.v2": ("click", "double_click", "long_click_press"),
    "lumi.sensor_switch.aq2": ("click", "double_click", "long_click_press"),
    "lumi.sensor_switch.aq3": ("click", "double_click", "long_click_press"),
    "lumi.sensor_switch.es2": ("click", "double_click", "long_click_press"),
    "lumi.sensor_switch.es3": ("click", "double_click", "long_click_press"),
    "lumi.sensor_86sw1.v1": ("click", "double_click", "long_click_press"),
    "lumi.remote.b1acn01": ("click", "double_click", "long_click_press"),
    "lumi.remote.b18ac1": ("click", "double_click", "long_click_press"),
    # wireless double switch
    "lumi.remote.b286acn02": (
        "button1-click",
        "button1-double_click",
        "button1-long_click_press",
        "button2-click",
        "button2-double_click",
        "button2-long_click_press",
    ),
    "lumi.remote.b1akr1": (
        "button1-click",
        "button1-double_click",
        "button1-long_click_press",
        "button2-click",
        "button2-double_click",
        "button2-long_click_press",
    ),
    "lumi.remote.acn002": (
        "button1-click",
        "button1-double_click",
        "button1-long_click_press",
        "button2-click",
        "button2-double_click",
        "button2-long_click_press",
    ),
    "lumi.remote.acn004": (
        "button1-click",
        "button1-double_click",
        "button1-long_click_press",
        "button2-click",
        "button2-double_click",
        "button2-long_click_press",
    ),
    "lumi.remote.acn009": (
        "button1-click",
        "button1-double_click",
        "button1-long_click_press",
        "button2-click",
        "button2-double_click",
        "button2-long_click_press",
    ),
    "lumi.switch.n2eic2": (
        "button1-click",
        "button1-double_click",
        "button1-long_click_press",
        "button2-click",
        "button2-double_click",
        "button2-long_click_press",
    ),
    "lumi.switch.n1eic2": (
        "button1-click",
        "button1-double_click",
        "button1-long_click_press",
        "button2-click",
        "button2-double_click",
        "button2-long_click_press",
    ),
    "lumi.remote.b286acn03": (
        "button1-click",
        "button1-double_click",
        "button1-long_click_press",
        "button2-click",
        "button2-double_click",
        "button2-long_click_press",
    ),
    "lumi.sensor_86sw2.v1": (
        "button1-click",
        "button1-double_click",
        "button1-long_click_press",
        "button2-click",
        "button2-double_click",
        "button2-long_click_press",
    ),
    "lumi.sensor_86sw2.es1": (
        "button1-click",
        "button1-double_click",
        "button1-long_click_press",
        "button2-click",
        "button2-double_click",
        "button2-long_click_press",
    ),
    "lumi.remote.b28ac1": (
        "button1-click",
        "button1-double_click",
        "button1-long_click_press",
        "button2-click",
        "button2-double_click",
        "button2-long_click_press",
    ),
    "lumi.remote.b286acn01": (
        "button1-click",
        "button1-double_click",
        "button1-long_click_press",
        "button2-click",
        "button2-double_click",
        "button2-long_click_press",
    ),
    "lumi.remote.b286opcn01": (
        "button1-click",
        "button1-double_click",
        "button1-long_click_press",
        "button2-click",
        "button2-double_click",
        "button2-long_click_press",
    ),
    "lumi.sensor_86sw2.aq1": (
        "button1-click",
        "button1-double_click",
        "button1-long_click_press",
        "button2-click",
        "button2-double_click",
        "button2-long_click_press",
    ),
}


# TODO specify your supported trigger types.
TRIGGER_TYPES = {triggerType for x in AQARA_EVENTS.values() for triggerType in x}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:

    """List device triggers for Aqara devices."""
    device_registry = dr.async_get(hass)
    device = device_registry.devices[device_id]

    triggers = []

    if device.model in AQARA_EVENTS_MAP:
        for trigger_type in AQARA_EVENTS.get(device.model):
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
    action: AutomationActionType,
    automation_info: AutomationTriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: "aqara_event",
            event_trigger.CONF_EVENT_DATA: {
                CONF_DEVICE_ID: config[CONF_DEVICE_ID],
                CONF_TYPE: config[CONF_TYPE],
            },
        }
    )
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, automation_info, platform_type="device"
    )
