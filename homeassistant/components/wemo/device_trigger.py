"""Triggers for WeMo devices."""
import voluptuous as vol

from homeassistant.components.device_automation import TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.helpers.entity_registry import async_entries_for_device

from .const import (
    CAPABILITY_LONG_PRESS,
    DOMAIN as WEMO_DOMAIN,
    TRIGGER_TYPE_LONG_PRESS,
    WEMO_EVENT,
)

TRIGGER_TYPES = {TRIGGER_TYPE_LONG_PRESS}

TRIGGER_SCHEMA = TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)


async def async_get_triggers(hass, device_id):
    """Return a list of triggers."""

    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    entity_entries = async_entries_for_device(entity_registry, device_id)

    triggers = []

    # Check for long press support.
    if any(
        entry.capabilities.get(CAPABILITY_LONG_PRESS)
        for entry in entity_entries
        if entry.capabilities
    ):
        triggers.append(
            {
                # Required fields of TRIGGER_BASE_SCHEMA
                CONF_PLATFORM: "device",
                CONF_DOMAIN: WEMO_DOMAIN,
                CONF_DEVICE_ID: device_id,
                # Required fields of TRIGGER_SCHEMA
                CONF_TYPE: TRIGGER_TYPE_LONG_PRESS,
            }
        )

    return triggers


async def async_attach_trigger(hass, config, action, automation_info):
    """Attach a trigger."""
    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: WEMO_EVENT,
            event_trigger.CONF_EVENT_DATA: {
                CONF_DEVICE_ID: config[CONF_DEVICE_ID],
                CONF_TYPE: config[CONF_TYPE],
            },
        }
    )
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, automation_info, platform_type="device"
    )
