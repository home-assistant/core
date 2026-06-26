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
    DATA_NOTIFY,
    DOMAIN,
)
from ..helpers import empty_okay_response
from ..webhook import WEBHOOK_COMMANDS, validate_schema
from .store import (
    pop_pending_update,
    remove_live_activity_token,
    store_live_activity_token,
)


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
    """Store a Live Activity push token sent by the app, flushing any buffered update."""
    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    tag = data[ATTR_TAG]
    # Read the buffer before storing the token, which clears the pending state.
    buffered = pop_pending_update(hass, webhook_id, tag)
    store_live_activity_token(
        hass,
        webhook_id,
        tag,
        data[ATTR_PUSH_TOKEN],
        data[ATTR_LIVE_ACTIVITY_EXPIRES_AT],
    )
    if buffered is not None and (service := hass.data[DOMAIN].get(DATA_NOTIFY)):
        # The token is now stored, so this resolves to an update.
        await service.async_send_remote_message_target(config_entry, buffered)
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
