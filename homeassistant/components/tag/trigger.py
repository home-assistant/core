"""Support for tag triggers."""
import voluptuous as vol

from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import CONF_PLATFORM
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import DEVICE_ID, DOMAIN, EVENT_TAG_SCANNED, TAG_ID

TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM): DOMAIN,
        vol.Required(TAG_ID): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(DEVICE_ID): cv.string,
    }
)


async def async_attach_trigger(hass, config, action, automation_info):
    """Listen for tag_scanned events based on configuration."""
    tag_ids = config.get(TAG_ID)
    device_id = config.get(DEVICE_ID)
    removes = []

    for tag_id in tag_ids:
        event_data = {TAG_ID: tag_id}
        if device_id:
            event_data[DEVICE_ID] = device_id

        event_config = {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: EVENT_TAG_SCANNED,
            event_trigger.CONF_EVENT_DATA: event_data,
        }
        event_config = event_trigger.TRIGGER_SCHEMA(event_config)

        removes.append(
            await event_trigger.async_attach_trigger(
                hass, event_config, action, automation_info, platform_type=DOMAIN
            )
        )

    @callback
    def remove_triggers():
        """Remove event triggers."""
        for remove in removes:
            remove()

    return remove_triggers
