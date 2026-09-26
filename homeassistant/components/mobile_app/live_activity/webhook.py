"""Live Activity webhook handlers."""

from typing import Any

from aiohttp.web import Response
import probatio

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from ..const import (
    ATTR_DEVICE_NAME,
    ATTR_LIVE_ACTIVITY_EXPIRES_AT,
    ATTR_PUSH_TOKEN,
    ATTR_TAG,
    DATA_DEVICES,
    DOMAIN,
    EVENT_LIVE_ACTIVITY_DISMISSED,
)
from ..helpers import empty_okay_response, registration_context
from ..webhook import WEBHOOK_COMMANDS, validate_schema
from .store import remove_live_activity_token, store_live_activity_token


@WEBHOOK_COMMANDS.register("live_activity_token")
@validate_schema(
    {
        probatio.Required(ATTR_TAG): cv.string,
        probatio.Required(ATTR_PUSH_TOKEN): cv.string,
        probatio.Required(ATTR_LIVE_ACTIVITY_EXPIRES_AT): cv.positive_float,
    }
)
async def webhook_update_live_activity_token(
    hass: HomeAssistant, config_entry: ConfigEntry, data: dict[str, Any]
) -> Response:
    """Store a Live Activity APNs token sent by the iOS app."""
    store_live_activity_token(
        hass,
        config_entry.data[CONF_WEBHOOK_ID],
        data[ATTR_TAG],
        data[ATTR_PUSH_TOKEN],
        data[ATTR_LIVE_ACTIVITY_EXPIRES_AT],
    )
    return empty_okay_response()


@WEBHOOK_COMMANDS.register("live_activity_dismissed")
@validate_schema(
    {
        probatio.Required(ATTR_TAG): cv.string,
    }
)
async def webhook_live_activity_dismissed(
    hass: HomeAssistant, config_entry: ConfigEntry, data: dict[str, str]
) -> Response:
    """Remove a stored Live Activity token and fire an event when dismissed."""
    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    remove_live_activity_token(hass, webhook_id, data[ATTR_TAG])
    hass.bus.async_fire(
        EVENT_LIVE_ACTIVITY_DISMISSED,
        {
            ATTR_TAG: data[ATTR_TAG],
            ATTR_DEVICE_ID: hass.data[DOMAIN][DATA_DEVICES][webhook_id].id,
            ATTR_DEVICE_NAME: config_entry.data[ATTR_DEVICE_NAME],
        },
        context=registration_context(config_entry.data),
    )
    return empty_okay_response()
