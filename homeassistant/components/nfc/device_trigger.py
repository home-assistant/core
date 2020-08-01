"""Provides device automations for nfc devices that emit events."""
import homeassistant.components.automation.event as event
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM

from .const import DOMAIN

DEVICE = "device"
NFC_TAG_DEVICE_ID = "nfc_tag_device_id"
EVENT = "nfc-tag-scanned"


async def async_validate_trigger_config(hass, config):
    """Validate config."""
    return config


async def async_attach_trigger(hass, config, action, automation_info):
    """Listen for state changes based on configuration."""
    event_config = {
        event.CONF_PLATFORM: "event",
        event.CONF_EVENT_TYPE: EVENT,
        event.CONF_EVENT_DATA: {NFC_TAG_DEVICE_ID: config[CONF_DEVICE_ID]},
    }

    event_config = event.TRIGGER_SCHEMA(event_config)
    return await event.async_attach_trigger(
        hass, event_config, action, automation_info, platform_type="device"
    )


async def async_get_triggers(hass, device_id):
    """List device triggers.

    Make sure the device supports device automations and
    if it does return the trigger list.
    """
    return [{CONF_DEVICE_ID: device_id, CONF_DOMAIN: DOMAIN, CONF_PLATFORM: DEVICE}]
