"""Support for tag triggers."""
import voluptuous as vol

from homeassistant.const import CONF_PLATFORM
from homeassistant.core import HassJob, callback
from homeassistant.helpers import config_validation as cv

from .const import DEVICE_ID, DOMAIN, EVENT_TAG_SCANNED, TAG_ID

TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM): DOMAIN,
        vol.Required(TAG_ID): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
    }
)


async def async_attach_trigger(hass, config, action, automation_info):
    """Listen for tag_scanned events based on configuration."""
    tag_ids = config.get(TAG_ID)
    device_ids = config.get(DEVICE_ID)

    tag_data_schema = vol.Schema(
        {
            vol.Required(TAG_ID): vol.In(tag_ids),
        },
        extra=vol.ALLOW_EXTRA,
    )

    if device_ids:
        tag_data_schema = tag_data_schema.extend(
            {
                vol.Required(DEVICE_ID): vol.In(device_ids),
            }
        )

    job = HassJob(action)

    @callback
    def handle_event(event):
        """Listen for tag scan events and calls the action when data matches."""
        try:
            tag_data_schema(event.data)
        except vol.Invalid:
            # If event doesn't match, skip tag event
            return

        hass.async_run_hass_job(
            job,
            {
                "trigger": {
                    "platform": DOMAIN,
                    "event": event,
                    "description": "Tag scanned",
                }
            },
            event.context,
        )

    return hass.bus.async_listen(EVENT_TAG_SCANNED, handle_event)
