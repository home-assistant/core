"""Mastodon platform for notify component."""
from __future__ import annotations

from typing import Any

from mastodon import Mastodon
from mastodon.Mastodon import MastodonAPIError, MastodonUnauthorizedError
import voluptuous as vol

from homeassistant.components.notify import PLATFORM_SCHEMA, BaseNotificationService
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_BASE_URL, DEFAULT_URL, LOGGER

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ACCESS_TOKEN): cv.string,
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
        vol.Optional(CONF_BASE_URL, default=DEFAULT_URL): cv.string,
    }
)


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> MastodonNotificationService | None:
    """Get the Mastodon notification service."""
    client_id = config.get(CONF_CLIENT_ID)
    client_secret = config.get(CONF_CLIENT_SECRET)
    access_token = config.get(CONF_ACCESS_TOKEN)
    base_url = config.get(CONF_BASE_URL)

    try:
        mastodon = Mastodon(
            client_id=client_id,
            client_secret=client_secret,
            access_token=access_token,
            api_base_url=base_url,
        )
        mastodon.account_verify_credentials()
    except MastodonUnauthorizedError:
        LOGGER.warning("Authentication failed")
        return None

    return MastodonNotificationService(mastodon)


class MastodonNotificationService(BaseNotificationService):
    """Implement the notification service for Mastodon."""

    def __init__(self, api: Mastodon) -> None:
        """Initialize the service."""
        self._api = api

    def send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to a user."""
        try:
            self._api.toot(message)
        except MastodonAPIError:
            LOGGER.error("Unable to send message")
