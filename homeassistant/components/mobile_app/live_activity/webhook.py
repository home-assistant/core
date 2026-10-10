"""Live Activity webhook handlers."""

from typing import Any

from aiohttp.web import Response
import probatio

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr

from ..const import (
    ATTR_LIVE_ACTIVITY_EXPIRES_AT,
    ATTR_PUSH_TOKEN,
    ATTR_TAG,
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
    remove_live_activity_token(hass, config_entry.data[CONF_WEBHOOK_ID], data[ATTR_TAG])
    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, config_entry.data[ATTR_DEVICE_ID]), config_entry.entry_id
    )
    hass.bus.async_fire(
        EVENT_LIVE_ACTIVITY_DISMISSED,
        {
            ATTR_TAG: data[ATTR_TAG],
            ATTR_DEVICE_ID: device.id if device else None,
        },
        context=registration_context(config_entry.data),
    )
    return empty_okay_response()
