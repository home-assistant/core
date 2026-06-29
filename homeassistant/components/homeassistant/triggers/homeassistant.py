"""Offer Home Assistant core automation rules."""

import voluptuous as vol

from homeassistant.const import CONF_EVENT, CONF_PLATFORM, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CALLBACK_TYPE, Event, HassJob, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from ..const import DOMAIN

EVENT_START = "start"
EVENT_SHUTDOWN = "shutdown"

TRIGGER_SCHEMA = cv.TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): DOMAIN,
        vol.Required(CONF_EVENT): vol.Any(EVENT_START, EVENT_SHUTDOWN),
    }
)


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Listen for events based on configuration."""
    trigger_data = trigger_info["trigger_data"]
    event = config.get(CONF_EVENT)
    job = HassJob(action, f"homeassistant trigger {trigger_info}")

    if event == EVENT_SHUTDOWN:
        return hass.async_add_shutdown_job(
            job,
            {
                "trigger": {
                    **trigger_data,
                    "platform": DOMAIN,
                    "event": event,
                    "description": "Home Assistant stopping",
                }
            },
        )

    @callback
    def hass_started(_: Event) -> None:
        hass.async_run_hass_job(
            job,
            {
                "trigger": {
                    **trigger_data,
                    "platform": DOMAIN,
                    "event": event,
                    "description": "Home Assistant starting",
                }
            },
        )

    # Only fires if armed before EVENT_HOMEASSISTANT_STARTED; if hass is already
    # started, the trigger doesn't fire.
    return hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, hass_started)
