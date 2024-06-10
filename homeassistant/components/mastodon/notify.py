"""Mastodon platform for notify component."""

from __future__ import annotations

import mimetypes
from typing import Any

from mastodon import Mastodon
from mastodon.Mastodon import MastodonAPIError, MastodonUnauthorizedError
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_BASE_URL, DEFAULT_URL, LOGGER

ATTR_MEDIA = "media"
ATTR_TARGET = "target"
ATTR_MEDIA_WARNING = "media_warning"
ATTR_CONTENT_WARNING = "content_warning"

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
        """Toot a message, with media perhaps."""
        data = kwargs.get(ATTR_DATA)

        media = None
        mediadata = None
        target = None
        sensitive = False
        content_warning = None

        if data:
            media = data.get(ATTR_MEDIA)
            if media:
                if not self.hass.config.is_allowed_path(media):
                    LOGGER.warning("'%s' is not a whitelisted directory", media)
                    return
                mediadata = self._upload_media(media)

            target = data.get(ATTR_TARGET)
            sensitive = data.get(ATTR_MEDIA_WARNING)
            content_warning = data.get(ATTR_CONTENT_WARNING)

        if mediadata:
            try:
                self._api.status_post(
                    message,
                    media_ids=mediadata["id"],
                    sensitive=sensitive,
                    visibility=target,
                    spoiler_text=content_warning,
                )
            except MastodonAPIError:
                LOGGER.error("Unable to send message")
        else:
            try:
                self._api.status_post(
                    message, visibility=target, spoiler_text=content_warning
                )
            except MastodonAPIError:
                LOGGER.error("Unable to send message")

    def _upload_media(self, media_path: Any = None) -> Any:
        """Upload media."""
        with open(media_path, "rb"):
            media_type = self._media_type(media_path)
        try:
            mediadata = self._api.media_post(media_path, mime_type=media_type)
        except MastodonAPIError:
            LOGGER.error(f"Unable to upload image {media_path}")

        return mediadata

    def _media_type(self, media_path: Any = None) -> Any:
        """Get media Type."""
        (media_type, _) = mimetypes.guess_type(media_path)

        return media_type
