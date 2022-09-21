"""Provides device automations for ZHA devices that emit events."""

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import HomeAssistantError, IntegrationError
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from . import DOMAIN as ZHA_DOMAIN
from .core.const import DATA_ZHA, ZHA_DEVICES_LOADED_EVENT, ZHA_EVENT
from .core.helpers import async_get_zha_device

CONF_SUBTYPE = "subtype"
DEVICE = "device"
DEVICE_IEEE = "device_ieee"

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {vol.Required(CONF_TYPE): str, vol.Required(CONF_SUBTYPE): str}
)


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    config = TRIGGER_SCHEMA(config)

    if ZHA_DOMAIN in hass.config.components:
        await hass.data[DATA_ZHA][ZHA_DEVICES_LOADED_EVENT].wait()
        trigger = (config[CONF_TYPE], config[CONF_SUBTYPE])
        try:
            zha_device = async_get_zha_device(hass, config[CONF_DEVICE_ID])
        except (KeyError, AttributeError, IntegrationError) as err:
            raise InvalidDeviceAutomationConfig from err
        if (
            zha_device.device_automation_triggers is None
            or trigger not in zha_device.device_automation_triggers
        ):
            raise InvalidDeviceAutomationConfig

    return config


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Listen for state changes based on configuration."""
    trigger_key: tuple[str, str] = (config[CONF_TYPE], config[CONF_SUBTYPE])
    try:
        zha_device = async_get_zha_device(hass, config[CONF_DEVICE_ID])
    except (KeyError, AttributeError) as err:
        raise HomeAssistantError(
            f"Unable to get zha device {config[CONF_DEVICE_ID]}"
        ) from err

    if trigger_key not in zha_device.device_automation_triggers:
        raise HomeAssistantError(f"Unable to find trigger {trigger_key}")

    trigger = zha_device.device_automation_triggers[trigger_key]

    event_config = {
        event_trigger.CONF_PLATFORM: "event",
        event_trigger.CONF_EVENT_TYPE: ZHA_EVENT,
        event_trigger.CONF_EVENT_DATA: {DEVICE_IEEE: str(zha_device.ieee), **trigger},
    }

    event_config = event_trigger.TRIGGER_SCHEMA(event_config)
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device triggers.

    Make sure the device supports device automations and
    if it does return the trigger list.
    """
    zha_device = async_get_zha_device(hass, device_id)

    if not zha_device.device_automation_triggers:
        return []

    triggers = []
    for trigger, subtype in zha_device.device_automation_triggers.keys():
        triggers.append(
            {
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: ZHA_DOMAIN,
                CONF_PLATFORM: DEVICE,
                CONF_TYPE: trigger,
                CONF_SUBTYPE: subtype,
            }
        )

    return triggers
