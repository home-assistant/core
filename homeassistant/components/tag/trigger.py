"""Support for tag triggers."""
import voluptuous as vol

from homeassistant.const import CONF_PLATFORM
from homeassistant.core import HassJob
from homeassistant.helpers import config_validation as cv

from .const import DEVICE_ID, DOMAIN, EVENT_TAG_SCANNED, TAG_ID

TRIGGER_SCHEMA = cv.TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): DOMAIN,
        vol.Required(TAG_ID): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
    }
)


async def async_attach_trigger(hass, config, action, automation_info):
    """Listen for tag_scanned events based on configuration."""
    trigger_data = automation_info.get("trigger_data", {}) if automation_info else {}
    tag_ids = set(config[TAG_ID])
    device_ids = set(config[DEVICE_ID]) if DEVICE_ID in config else None

    job = HassJob(action)

    async def handle_event(event):
        """Listen for tag scan events and calls the action when data matches."""
        if event.data.get(TAG_ID) not in tag_ids or (
            device_ids is not None and event.data.get(DEVICE_ID) not in device_ids
        ):
            return

        task = hass.async_run_hass_job(
            job,
            {
                "trigger": {
                    **trigger_data,
                    "platform": DOMAIN,
                    "event": event,
                    "description": "Tag scanned",
                }
            },
            event.context,
        )

        if task:
            await task

    return hass.bus.async_listen(EVENT_TAG_SCANNED, handle_event)
