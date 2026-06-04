"""Live Activity webhook handlers."""
# pylint: disable=home-assistant-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

from collections.abc import Callable, Coroutine
import logging
from typing import Any

from aiohttp.web import Response
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.util.decorator import Registry

from ..const import (
    ATTR_LIVE_ACTIVITY_EXPIRES_AT,
    ATTR_LIVE_ACTIVITY_TAG,
    ATTR_PUSH_TOKEN,
)
from ..helpers import empty_okay_response
from . import remove_live_activity_token, store_live_activity_token

_LOGGER = logging.getLogger(__name__)

WebhookCommand = Callable[
    [HomeAssistant, ConfigEntry, Any], Coroutine[Any, Any, Response]
]
ValidateSchema = Callable[[Any], Callable[[WebhookCommand], WebhookCommand]]


def register_live_activity_webhook_commands(
    webhook_commands: Registry[str, WebhookCommand],
    validate_schema: ValidateSchema,
) -> None:
    """Register Live Activity webhook commands."""

    @webhook_commands.register("live_activity_token")
    @validate_schema(
        {
            vol.Required(ATTR_LIVE_ACTIVITY_TAG): cv.string,
            vol.Required(ATTR_PUSH_TOKEN): cv.string,
            vol.Required(ATTR_LIVE_ACTIVITY_EXPIRES_AT): cv.positive_float,
        }
    )
    async def webhook_update_live_activity_token(
        hass: HomeAssistant, config_entry: ConfigEntry, data: dict[str, Any]
    ) -> Response:
        """Store a Live Activity APNs token sent by the iOS app."""
        webhook_id = config_entry.data[CONF_WEBHOOK_ID]
        store_live_activity_token(
            hass,
            webhook_id,
            data[ATTR_LIVE_ACTIVITY_TAG],
            data[ATTR_PUSH_TOKEN],
            data[ATTR_LIVE_ACTIVITY_EXPIRES_AT],
        )

        return empty_okay_response()

    @webhook_commands.register("live_activity_dismissed")
    @validate_schema(
        {
            vol.Required(ATTR_LIVE_ACTIVITY_TAG): cv.string,
        }
    )
    async def webhook_live_activity_dismissed(
        hass: HomeAssistant, config_entry: ConfigEntry, data: dict[str, str]
    ) -> Response:
        """Remove a stored Live Activity token when the activity ends on device."""
        webhook_id = config_entry.data[CONF_WEBHOOK_ID]
        activity_tag = data[ATTR_LIVE_ACTIVITY_TAG]

        if not remove_live_activity_token(hass, webhook_id, activity_tag):
            # Typically means the token already expired via the cleanup loop or
            # the activity predates this code shipping — both expected, not a bug.
            _LOGGER.debug(
                (
                    "Received live_activity_dismissed for tag %s but no tokens "
                    "stored for webhook %s"
                ),
                activity_tag,
                webhook_id,
            )

        return empty_okay_response()
