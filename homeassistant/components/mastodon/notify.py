"""Mastodon platform for notify component."""

from __future__ import annotations

from typing import Any, cast

from mastodon import Mastodon
from mastodon.Mastodon import MastodonAPIError, MediaAttachment
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    ATTR_CONTENT_WARNING,
    ATTR_MEDIA_WARNING,
    CONF_BASE_URL,
    DEFAULT_URL,
    DOMAIN,
)
from .utils import get_media_type

ATTR_MEDIA = "media"
ATTR_TARGET = "target"

PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ACCESS_TOKEN): cv.string,
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
        vol.Optional(CONF_BASE_URL, default=DEFAULT_URL): cv.string,
    }
)

INTEGRATION_TITLE = "Mastodon"


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> MastodonNotificationService | None:
    """Get the Mastodon notification service."""
    if discovery_info is None:
        return None

    client = cast(Mastodon, discovery_info.get("client"))

    return MastodonNotificationService(hass, client)


class MastodonNotificationService(BaseNotificationService):
    """Implement the notification service for Mastodon."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: Mastodon,
    ) -> None:
        """Initialize the service."""

        self.client = client

    def send_message(self, message: str = "", **kwargs: Any) -> None:
        """Toot a message, with media perhaps."""

        ir.create_issue(
            self.hass,
            DOMAIN,
            "deprecated_notify_action_mastodon",
            breaks_in_ha_version="2025.9.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_notify_action",
        )

        target = None
        if (target_list := kwargs.get(ATTR_TARGET)) is not None:
            target = cast(list[str], target_list)[0]

        data = kwargs.get(ATTR_DATA)

        media = None
        mediadata = None
        sensitive = False
        content_warning = None

        if data:
            media = data.get(ATTR_MEDIA)
            if media:
                if not self.hass.config.is_allowed_path(media):
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="not_whitelisted_directory",
                        translation_placeholders={"media": media},
                    )
                mediadata = self._upload_media(media)

            sensitive = data.get(ATTR_MEDIA_WARNING)
            content_warning = data.get(ATTR_CONTENT_WARNING)

        if mediadata:
            try:
                self.client.status_post(
                    message,
                    visibility=target,
                    spoiler_text=content_warning,
                    media_ids=mediadata.id,
                    sensitive=sensitive,
                )
            except MastodonAPIError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="unable_to_send_message",
                ) from err

        else:
            try:
                self.client.status_post(
                    message, visibility=target, spoiler_text=content_warning
                )
            except MastodonAPIError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="unable_to_send_message",
                ) from err

    def _upload_media(self, media_path: Any = None) -> MediaAttachment:
        """Upload media."""
        with open(media_path, "rb"):
            media_type = get_media_type(media_path)
        try:
            mediadata: MediaAttachment = self.client.media_post(
                media_path, mime_type=media_type
            )
        except MastodonAPIError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unable_to_upload_image",
                translation_placeholders={"media_path": media_path},
            ) from err

        return mediadata
