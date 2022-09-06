"""Provides device automations for Xiaomi Miio."""
import logging

from miio import Gateway
import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, KEY_DEVICE

_LOGGER = logging.getLogger(__name__)

TRIGGER_TYPES = {"water_detected", "noise_detected"}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): str,
    }
)


async def async_get_triggers(hass, device_id):
    """Return a list of triggers."""
    device_registry = dr.async_get(hass)
    device = device_registry.devices[device_id]

    triggers = []

    for config_entry_id in device.config_entries:
        entry_data = hass.data[DOMAIN].get(config_entry_id)
        if entry_data is not None:
            break

    if entry_data is None:
        _LOGGER.error("Xiaomi Miio device triggers: failed to get entry data")
        return triggers

    miio_device = entry_data[KEY_DEVICE]
    if isinstance(miio_device, Gateway):
        if device.via_device_id is None:  # gateway
            triggers.append(
                {
                    CONF_DEVICE_ID: device_id,
                    CONF_DOMAIN: DOMAIN,
                    CONF_PLATFORM: "device",
                    CONF_TYPE: "alarm_triggering",
                }
            )
        else:  # subdevice
            for identifier in device.identifiers:
                if identifier[0] == DOMAIN:
                    sid = identifier[1]
                    break

            subdevice = miio_device.devices[sid]
            for trigger in subdevice.push_events.keys():
                triggers.append(
                    {
                        CONF_DEVICE_ID: device_id,
                        CONF_DOMAIN: DOMAIN,
                        CONF_PLATFORM: "device",
                        CONF_TYPE: trigger,
                    }
                )

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: f"{DOMAIN}_event",
            event_trigger.CONF_EVENT_DATA: {
                CONF_DEVICE_ID: config[CONF_DEVICE_ID],
                CONF_TYPE: config[CONF_TYPE],
            },
        }
    )

    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )
