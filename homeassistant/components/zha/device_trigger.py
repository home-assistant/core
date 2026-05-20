"""Provides device automations for ZHA devices that emit events."""

from typing import Any

import voluptuous as vol
from zha.application.const import ZHA_EVENT

from homeassistant.components.device_automation import (
    DEVICE_TRIGGER_BASE_SCHEMA,
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .helpers import async_get_zha_device_proxy, get_zha_data

CONF_SUBTYPE = "subtype"
DEVICE = "device"
DEVICE_IEEE = "device_ieee"

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {vol.Required(CONF_TYPE): str, vol.Required(CONF_SUBTYPE): str}
)


def _to_native(obj: Any) -> Any:
    """Recursively convert zigpy named types to plain Python primitives.

    ZHA trigger data may contain zigpy types such as ClusterId that are int
    subclasses but are not accepted by voluptuous as schema values, causing
    SchemaError when event_trigger tries to build the event-data filter schema.
    LVList and other list subclasses are handled so nested zigpy types inside
    list-valued params are also converted.
    """
    if isinstance(obj, dict):
        return {k: _to_native(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_native(v) for v in obj]
    if isinstance(obj, bool):
        # bool is an int subclass; plain True/False fail as voluptuous schema values
        return int(obj)
    if isinstance(obj, int):
        return int(obj)
    if isinstance(obj, float):
        return float(obj)
    return obj


def _get_device_trigger_data(hass: HomeAssistant, device_id: str) -> tuple[str, dict]:
    """Get device trigger data for a device, falling back to the cache if possible."""

    # First, try checking to see if the device itself is accessible
    try:
        zha_device = async_get_zha_device_proxy(hass, device_id).device
    except ValueError:
        pass
    else:
        return str(zha_device.ieee), zha_device.device_automation_triggers

    # If not, check the trigger cache but allow any `KeyError`s to propagate
    return get_zha_data(hass).device_trigger_cache[device_id]


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    config = TRIGGER_SCHEMA(config)

    # Trigger validation will not occur if the config entry is not loaded
    _, triggers = _get_device_trigger_data(hass, config[CONF_DEVICE_ID])

    trigger = (config[CONF_TYPE], config[CONF_SUBTYPE])
    if trigger not in triggers:
        raise InvalidDeviceAutomationConfig(f"device does not have trigger {trigger}")

    return config


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Listen for state changes based on configuration."""

    try:
        ieee, triggers = _get_device_trigger_data(hass, config[CONF_DEVICE_ID])
    except KeyError as err:
        raise HomeAssistantError(
            f"Unable to get zha device {config[CONF_DEVICE_ID]}"
        ) from err

    trigger_key: tuple[str, str] = (config[CONF_TYPE], config[CONF_SUBTYPE])

    if trigger_key not in triggers:
        raise HomeAssistantError(f"Unable to find trigger {trigger_key}")

    # Convert zigpy named types (e.g. ClusterId) to plain Python primitives so
    # that voluptuous can use the values as schema literals without SchemaError.
    trigger_data = _to_native(triggers[trigger_key])

    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: ZHA_EVENT,
            event_trigger.CONF_EVENT_DATA: {DEVICE_IEEE: ieee, **trigger_data},
        }
    )

    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device triggers.

    Make sure the device supports device automations and return the trigger list.
    """
    try:
        _, triggers = _get_device_trigger_data(hass, device_id)
    except KeyError as err:
        raise InvalidDeviceAutomationConfig from err

    return [
        {
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_PLATFORM: DEVICE,
            CONF_TYPE: trigger,
            CONF_SUBTYPE: subtype,
        }
        for trigger, subtype in triggers
    ]
