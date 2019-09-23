"""Provides device automations for ZHA devices that emit events."""
import voluptuous as vol

import homeassistant.components.automation.event as event
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE

from . import DOMAIN
from .core.const import DATA_ZHA, DATA_ZHA_GATEWAY
from .core.helpers import convert_ieee

CONF_SUBTYPE = "subtype"
DEVICE = "device"
DEVICE_IEEE = "device_ieee"
ZHA_EVENT = "zha_event"

TRIGGER_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_DEVICE_ID): str,
            vol.Required(CONF_DOMAIN): DOMAIN,
            vol.Required(CONF_PLATFORM): DEVICE,
            vol.Required(CONF_TYPE): str,
            vol.Required(CONF_SUBTYPE): str,
        }
    )
)


async def async_trigger(hass, config, action, automation_info):
    """Listen for state changes based on configuration."""
    config = TRIGGER_SCHEMA(config)
    trigger = (config[CONF_TYPE], config[CONF_SUBTYPE])
    zha_device = await _async_get_zha_device(hass, config[CONF_DEVICE_ID])

    if (
        zha_device.device_automation_triggers is None
        or trigger not in zha_device.device_automation_triggers
    ):
        raise InvalidDeviceAutomationConfig

    trigger = zha_device.device_automation_triggers[trigger]

    state_config = {
        event.CONF_EVENT_TYPE: ZHA_EVENT,
        event.CONF_EVENT_DATA: {DEVICE_IEEE: str(zha_device.ieee), **trigger},
    }

    return await event.async_trigger(hass, state_config, action, automation_info)


async def async_get_triggers(hass, device_id):
    """List device triggers.

    Make sure the device supports device automations and
    if it does return the trigger list.
    """
    zha_device = await _async_get_zha_device(hass, device_id)

    if not zha_device.device_automation_triggers:
        return

    triggers = []
    for trigger, subtype in zha_device.device_automation_triggers.keys():
        triggers.append(
            {
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_PLATFORM: DEVICE,
                CONF_TYPE: trigger,
                CONF_SUBTYPE: subtype,
            }
        )

    return triggers


async def _async_get_zha_device(hass, device_id):
    device_registry = await hass.helpers.device_registry.async_get_registry()
    registry_device = device_registry.async_get(device_id)
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    ieee_address = list(list(registry_device.identifiers)[0])[1]
    ieee = convert_ieee(ieee_address)
    zha_device = zha_gateway.devices[ieee]
    if not zha_device:
        raise InvalidDeviceAutomationConfig
    return zha_device
