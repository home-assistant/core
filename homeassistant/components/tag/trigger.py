"""Support for tag triggers."""
import voluptuous as vol

from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import CONF_PLATFORM
from homeassistant.helpers import config_validation as cv

from .const import DEVICE_ID, DOMAIN, EVENT_TAG_SCANNED, TAG_ID

TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM): DOMAIN,
        vol.Required(TAG_ID): cv.string,
        vol.Optional(DEVICE_ID): cv.string,
    }
)


async def async_attach_trigger(hass, config, action, automation_info):
    """Listen for tag_scanned events based on configuration."""
    tag_id = config.get(TAG_ID)
    device_id = config.get(DEVICE_ID)
    event_data = {TAG_ID: tag_id}

    if device_id:
        event_data[DEVICE_ID] = device_id

    event_config = {
        event_trigger.CONF_PLATFORM: "event",
        event_trigger.CONF_EVENT_TYPE: EVENT_TAG_SCANNED,
        event_trigger.CONF_EVENT_DATA: event_data,
    }
    event_config = event_trigger.TRIGGER_SCHEMA(event_config)

    return await event_trigger.async_attach_trigger(
        hass, event_config, action, automation_info, platform_type=DOMAIN
    )
