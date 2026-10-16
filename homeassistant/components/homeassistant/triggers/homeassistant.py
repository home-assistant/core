"""Offer Home Assistant core automation rules."""

import probatio

from homeassistant.config import DATA_PREVIOUS_VERSION
from homeassistant.const import (
    CONF_EVENT,
    CONF_PLATFORM,
    EVENT_HOMEASSISTANT_STARTED,
    __version__,
)
from homeassistant.core import CALLBACK_TYPE, Event, HassJob, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from ..const import DOMAIN

EVENT_START = "start"
EVENT_SHUTDOWN = "shutdown"
EVENT_UPDATED = "updated"

TRIGGER_SCHEMA = cv.TRIGGER_BASE_SCHEMA.extend(
    {
        probatio.Required(CONF_PLATFORM): DOMAIN,
        probatio.Required(CONF_EVENT): probatio.Any(
            EVENT_START, EVENT_SHUTDOWN, EVENT_UPDATED
        ),
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

    unsub: CALLBACK_TYPE | None = None

    @callback
    def hass_started(_: Event) -> None:
        nonlocal unsub
        unsub = None

        if event == EVENT_UPDATED:
            # A downgrade, like restoring an older backup, counts as well
            if (previous_version := hass.data.get(DATA_PREVIOUS_VERSION)) is None:
                return
            hass.async_run_hass_job(
                job,
                {
                    "trigger": {
                        **trigger_data,
                        "platform": DOMAIN,
                        "event": event,
                        "description": "Home Assistant updated",
                        "from_version": previous_version,
                        "to_version": __version__,
                    }
                },
            )
            return

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
    unsub = hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, hass_started)

    @callback
    def remove() -> None:
        if unsub is not None:
            unsub()

    return remove
