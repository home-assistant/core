"""Live Activity webhook handlers."""
# pylint: disable=home-assistant-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

from typing import Any

from aiohttp.web import Response
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from ..const import (
    ATTR_LIVE_ACTIVITY_EXPIRES_AT,
    ATTR_PUSH_TOKEN,
    ATTR_TAG,
    ATTR_WEBHOOK_ID,
    EVENT_LIVE_ACTIVITY_STARTED,
)
from ..helpers import empty_okay_response
from ..webhook import WEBHOOK_COMMANDS, validate_schema
from .store import remove_live_activity_token, store_live_activity_token


@WEBHOOK_COMMANDS.register("live_activity_token")
@validate_schema(
    {
        vol.Required(ATTR_TAG): cv.string,
        vol.Required(ATTR_PUSH_TOKEN): cv.string,
        vol.Required(ATTR_LIVE_ACTIVITY_EXPIRES_AT): cv.positive_float,
    }
)
async def webhook_update_live_activity_token(
    hass: HomeAssistant, config_entry: ConfigEntry, data: dict[str, Any]
) -> Response:
    """Store a Live Activity APNs token sent by the iOS app.

    Fires ``mobile_app_live_activity_started`` after the token is stored so
    automations can react to the device confirming receipt of the START push,
    for example by re-emitting the current state as an update.
    """
    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    tag = data[ATTR_TAG]
    store_live_activity_token(
        hass,
        webhook_id,
        tag,
        data[ATTR_PUSH_TOKEN],
        data[ATTR_LIVE_ACTIVITY_EXPIRES_AT],
    )
    hass.bus.async_fire(
        EVENT_LIVE_ACTIVITY_STARTED,
        {ATTR_WEBHOOK_ID: webhook_id, ATTR_TAG: tag},
    )
    return empty_okay_response()


@WEBHOOK_COMMANDS.register("live_activity_dismissed")
@validate_schema(
    {
        vol.Required(ATTR_TAG): cv.string,
    }
)
async def webhook_live_activity_dismissed(
    hass: HomeAssistant, config_entry: ConfigEntry, data: dict[str, str]
) -> Response:
    """Remove a stored Live Activity token when the activity ends on device."""
    remove_live_activity_token(hass, config_entry.data[CONF_WEBHOOK_ID], data[ATTR_TAG])
    return empty_okay_response()
