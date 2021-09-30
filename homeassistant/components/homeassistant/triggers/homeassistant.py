"""Offer Home Assistant core automation rules."""
import voluptuous as vol

from homeassistant.const import CONF_EVENT, CONF_PLATFORM, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HassJob, callback
from homeassistant.helpers import config_validation as cv

# mypy: allow-untyped-defs

EVENT_START = "start"
EVENT_SHUTDOWN = "shutdown"

TRIGGER_SCHEMA = cv.TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): "homeassistant",
        vol.Required(CONF_EVENT): vol.Any(EVENT_START, EVENT_SHUTDOWN),
    }
)


async def async_attach_trigger(hass, config, action, automation_info):
    """Listen for events based on configuration."""
    trigger_data = automation_info.get("trigger_data", {}) if automation_info else {}
    event = config.get(CONF_EVENT)
    job = HassJob(action)

    if event == EVENT_SHUTDOWN:

        @callback
        def hass_shutdown(event):
            """Execute when Home Assistant is shutting down."""
            hass.async_run_hass_job(
                job,
                {
                    "trigger": {
                        **trigger_data,
                        "platform": "homeassistant",
                        "event": event,
                        "description": "Home Assistant stopping",
                    }
                },
                event.context,
            )

        return hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, hass_shutdown)

    # Automation are enabled while hass is starting up, fire right away
    # Check state because a config reload shouldn't trigger it.
    if automation_info["home_assistant_start"]:
        hass.async_run_hass_job(
            job,
            {
                "trigger": {
                    **trigger_data,
                    "platform": "homeassistant",
                    "event": event,
                    "description": "Home Assistant starting",
                }
            },
        )

    return lambda: None
