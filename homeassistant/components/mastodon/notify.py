"""Mastodon platform for notify component."""

from __future__ import annotations

import mimetypes
from typing import Any, cast

from mastodon import Mastodon
from mastodon.Mastodon import MastodonAPIError
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_BASE_URL, DEFAULT_URL, DOMAIN, LOGGER

ATTR_MEDIA = "media"
ATTR_TARGET = "target"
ATTR_MEDIA_WARNING = "media_warning"
ATTR_CONTENT_WARNING = "content_warning"

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

    if not discovery_info:
        # Import config entry

        import_result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )

        if (
            import_result["type"] == FlowResultType.ABORT
            and import_result["reason"] != "already_configured"
        ):
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"deprecated_yaml_import_issue_{import_result["reason"]}",
                breaks_in_ha_version="2025.2.0",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.WARNING,
                translation_key=f"deprecated_yaml_import_issue_{import_result["reason"]}",
                translation_placeholders={
                    "domain": DOMAIN,
                    "integration_title": INTEGRATION_TITLE,
                },
            )
            return None

        ir.async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2025.2.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": INTEGRATION_TITLE,
            },
        )

        return None

    client: Mastodon = discovery_info.get("client")

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
                    LOGGER.warning("'%s' is not a whitelisted directory", media)
                    return
                mediadata = self._upload_media(media)

            sensitive = data.get(ATTR_MEDIA_WARNING)
            content_warning = data.get(ATTR_CONTENT_WARNING)

        if mediadata:
            try:
                self.client.status_post(
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
                self.client.status_post(
                    message, visibility=target, spoiler_text=content_warning
                )
            except MastodonAPIError:
                LOGGER.error("Unable to send message")

    def _upload_media(self, media_path: Any = None) -> Any:
        """Upload media."""
        with open(media_path, "rb"):
            media_type = self._media_type(media_path)
        try:
            mediadata = self.client.media_post(media_path, mime_type=media_type)
        except MastodonAPIError:
            LOGGER.error(f"Unable to upload image {media_path}")

        return mediadata

    def _media_type(self, media_path: Any = None) -> Any:
        """Get media Type."""
        (media_type, _) = mimetypes.guess_type(media_path)

        return media_type
