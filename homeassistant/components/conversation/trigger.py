"""Offer sentence based automation rules."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.const import (
    CONF_COMMAND,
    CONF_PLATFORM,
)
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from . import async_register_trigger_sentences
from .const import CONF_RESPONSE, DOMAIN

TRIGGER_SCHEMA = cv.TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): DOMAIN,
        vol.Required(CONF_COMMAND): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_RESPONSE): cv.string,
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
    sentences = config.get(CONF_COMMAND, [])
    response = config.get(CONF_RESPONSE)

    job = HassJob(action)

    @callback
    def call_action() -> None:
        """Call action with right context."""
        hass.async_run_hass_job(
            job,
            {
                "trigger": {
                    **trigger_data,
                    "platform": DOMAIN,
                    "sentences": sentences,
                    "response": response,
                }
            },
        )

    return await async_register_trigger_sentences(
        hass,
        sentences,
        call_action,
        response=response,
    )
