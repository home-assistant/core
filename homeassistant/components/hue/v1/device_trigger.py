"""Provides device automations for Philips Hue events in V1 bridge/api."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_EVENT,
    CONF_PLATFORM,
    CONF_TYPE,
    CONF_UNIQUE_ID,
)
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from ..const import ATTR_HUE_EVENT, CONF_SUBTYPE, DOMAIN

if TYPE_CHECKING:
    from ..bridge import HueBridge

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {vol.Required(CONF_TYPE): str, vol.Required(CONF_SUBTYPE): str}
)


CONF_SHORT_PRESS = "remote_button_short_press"
CONF_SHORT_RELEASE = "remote_button_short_release"
CONF_LONG_RELEASE = "remote_button_long_release"
CONF_DOUBLE_SHORT_RELEASE = "remote_double_button_short_press"
CONF_DOUBLE_LONG_RELEASE = "remote_double_button_long_press"

CONF_TURN_ON = "turn_on"
CONF_TURN_OFF = "turn_off"
CONF_DIM_UP = "dim_up"
CONF_DIM_DOWN = "dim_down"
CONF_BUTTON_1 = "button_1"
CONF_BUTTON_2 = "button_2"
CONF_BUTTON_3 = "button_3"
CONF_BUTTON_4 = "button_4"
CONF_DOUBLE_BUTTON_1 = "double_buttons_1_3"
CONF_DOUBLE_BUTTON_2 = "double_buttons_2_4"

HUE_DIMMER_REMOTE_MODEL = "Hue dimmer switch"  # RWL020/021
HUE_DIMMER_REMOTE = {
    (CONF_SHORT_RELEASE, CONF_TURN_ON): {CONF_EVENT: 1002},
    (CONF_LONG_RELEASE, CONF_TURN_ON): {CONF_EVENT: 1003},
    (CONF_SHORT_RELEASE, CONF_DIM_UP): {CONF_EVENT: 2002},
    (CONF_LONG_RELEASE, CONF_DIM_UP): {CONF_EVENT: 2003},
    (CONF_SHORT_RELEASE, CONF_DIM_DOWN): {CONF_EVENT: 3002},
    (CONF_LONG_RELEASE, CONF_DIM_DOWN): {CONF_EVENT: 3003},
    (CONF_SHORT_RELEASE, CONF_TURN_OFF): {CONF_EVENT: 4002},
    (CONF_LONG_RELEASE, CONF_TURN_OFF): {CONF_EVENT: 4003},
}

HUE_BUTTON_REMOTE_MODEL = "Hue Smart button"  # ZLLSWITCH/ROM001
HUE_BUTTON_REMOTE = {
    (CONF_SHORT_RELEASE, CONF_TURN_ON): {CONF_EVENT: 1002},
    (CONF_LONG_RELEASE, CONF_TURN_ON): {CONF_EVENT: 1003},
}

HUE_WALL_REMOTE_MODEL = "Hue wall switch module"  # ZLLSWITCH/RDM001
HUE_WALL_REMOTE = {
    (CONF_SHORT_RELEASE, CONF_BUTTON_1): {CONF_EVENT: 1002},
    (CONF_SHORT_RELEASE, CONF_BUTTON_2): {CONF_EVENT: 2002},
}

HUE_TAP_REMOTE_MODEL = "Hue tap switch"  # ZGPSWITCH
HUE_TAP_REMOTE = {
    (CONF_SHORT_PRESS, CONF_BUTTON_1): {CONF_EVENT: 34},
    (CONF_SHORT_PRESS, CONF_BUTTON_2): {CONF_EVENT: 16},
    (CONF_SHORT_PRESS, CONF_BUTTON_3): {CONF_EVENT: 17},
    (CONF_SHORT_PRESS, CONF_BUTTON_4): {CONF_EVENT: 18},
}

HUE_FOHSWITCH_REMOTE_MODEL = "Friends of Hue Switch"  # ZGPSWITCH
HUE_FOHSWITCH_REMOTE = {
    (CONF_SHORT_PRESS, CONF_BUTTON_1): {CONF_EVENT: 20},
    (CONF_LONG_RELEASE, CONF_BUTTON_1): {CONF_EVENT: 16},
    (CONF_SHORT_PRESS, CONF_BUTTON_2): {CONF_EVENT: 21},
    (CONF_LONG_RELEASE, CONF_BUTTON_2): {CONF_EVENT: 17},
    (CONF_SHORT_PRESS, CONF_BUTTON_3): {CONF_EVENT: 23},
    (CONF_LONG_RELEASE, CONF_BUTTON_3): {CONF_EVENT: 19},
    (CONF_SHORT_PRESS, CONF_BUTTON_4): {CONF_EVENT: 22},
    (CONF_LONG_RELEASE, CONF_BUTTON_4): {CONF_EVENT: 18},
    (CONF_DOUBLE_SHORT_RELEASE, CONF_DOUBLE_BUTTON_1): {CONF_EVENT: 101},
    (CONF_DOUBLE_LONG_RELEASE, CONF_DOUBLE_BUTTON_1): {CONF_EVENT: 100},
    (CONF_DOUBLE_SHORT_RELEASE, CONF_DOUBLE_BUTTON_2): {CONF_EVENT: 99},
    (CONF_DOUBLE_LONG_RELEASE, CONF_DOUBLE_BUTTON_2): {CONF_EVENT: 98},
}


REMOTES: dict[str, dict[tuple[str, str], dict[str, int]]] = {
    HUE_DIMMER_REMOTE_MODEL: HUE_DIMMER_REMOTE,
    HUE_TAP_REMOTE_MODEL: HUE_TAP_REMOTE,
    HUE_BUTTON_REMOTE_MODEL: HUE_BUTTON_REMOTE,
    HUE_WALL_REMOTE_MODEL: HUE_WALL_REMOTE,
    HUE_FOHSWITCH_REMOTE_MODEL: HUE_FOHSWITCH_REMOTE,
}


def _get_hue_event_from_device_id(hass, device_id):
    """Resolve hue event from device id."""
    for bridge in hass.data.get(DOMAIN, {}).values():
        for hue_event in bridge.sensor_manager.current_events.values():
            if device_id == hue_event.device_registry_id:
                return hue_event

    return None


async def async_validate_trigger_config(
    bridge: HueBridge, device_entry: DeviceEntry, config: ConfigType
) -> ConfigType:
    """Validate config."""
    config = TRIGGER_SCHEMA(config)
    trigger = (config[CONF_TYPE], config[CONF_SUBTYPE])

    if not device_entry:
        raise InvalidDeviceAutomationConfig(
            f"Device {config[CONF_DEVICE_ID]} not found"
        )

    if device_entry.model not in REMOTES:
        raise InvalidDeviceAutomationConfig(
            f"Device model {device_entry.model} is not a remote"
        )

    if trigger not in REMOTES[device_entry.model]:
        raise InvalidDeviceAutomationConfig(
            f"Device does not support trigger {trigger}"
        )

    return config


async def async_attach_trigger(
    bridge: HueBridge,
    device_entry: DeviceEntry,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Listen for state changes based on configuration."""
    hass = bridge.hass

    hue_event = _get_hue_event_from_device_id(hass, device_entry.id)
    if hue_event is None:
        raise InvalidDeviceAutomationConfig

    trigger_key: tuple[str, str] = (config[CONF_TYPE], config[CONF_SUBTYPE])

    assert device_entry.model
    trigger = REMOTES[device_entry.model][trigger_key]

    event_config = {
        event_trigger.CONF_PLATFORM: "event",
        event_trigger.CONF_EVENT_TYPE: ATTR_HUE_EVENT,
        event_trigger.CONF_EVENT_DATA: {CONF_UNIQUE_ID: hue_event.unique_id, **trigger},
    }

    event_config = event_trigger.TRIGGER_SCHEMA(event_config)
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )


@callback
def async_get_triggers(bridge: HueBridge, device: DeviceEntry) -> list[dict[str, str]]:
    """Return device triggers for device on `v1` bridge.

    Make sure device is a supported remote model.
    Retrieve the hue event object matching device entry.
    Generate device trigger list.
    """
    if device.model not in REMOTES:
        return []

    triggers = []
    for trigger, subtype in REMOTES[device.model]:
        triggers.append(
            {
                CONF_DEVICE_ID: device.id,
                CONF_DOMAIN: DOMAIN,
                CONF_PLATFORM: "device",
                CONF_TYPE: trigger,
                CONF_SUBTYPE: subtype,
            }
        )

    return triggers
