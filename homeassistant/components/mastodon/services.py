"""Define services for the Mastodon integration."""

from enum import StrEnum
from functools import partial
import mimetypes
from typing import Any, cast

from mastodon import Mastodon
from mastodon.Mastodon import MastodonAPIError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from . import MastodonConfigEntry
from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_CONTENT_WARNING,
    ATTR_MEDIA,
    ATTR_MEDIA_WARNING,
    ATTR_STATUS,
    ATTR_VISIBILITY,
    DOMAIN,
)


class StatusVisibility(StrEnum):
    """StatusVisibility model."""

    PUBLIC = "public"
    UNLISTED = "unlisted"
    PRIVATE = "private"
    DIRECT = "direct"


SERVICE_POST = "post"
SERVICE_POST_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): str,
        vol.Required(ATTR_STATUS): str,
        vol.Optional(ATTR_VISIBILITY): vol.In([x.lower() for x in StatusVisibility]),
        vol.Optional(ATTR_CONTENT_WARNING): bool,
        vol.Optional(ATTR_MEDIA): str,
        vol.Optional(ATTR_MEDIA_WARNING): bool,
    }
)


def async_get_entry(hass: HomeAssistant, config_entry_id: str) -> MastodonConfigEntry:
    """Get the Mastodon config entry."""
    if not (entry := hass.config_entries.async_get_entry(config_entry_id)):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="integration_not_found",
            translation_placeholders={"target": DOMAIN},
        )
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_loaded",
            translation_placeholders={"target": entry.title},
        )
    return cast(MastodonConfigEntry, entry)


def setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Mastodon integration."""

    async def async_post(call: ServiceCall) -> ServiceResponse:
        """Post a status."""
        entry = async_get_entry(hass, call.data[ATTR_CONFIG_ENTRY_ID])
        client = entry.runtime_data.client

        status = call.data[ATTR_STATUS]

        visibility = None
        if ATTR_VISIBILITY in call.data:
            visibility = StatusVisibility(call.data[ATTR_VISIBILITY])
        content_warning = None
        if ATTR_CONTENT_WARNING in call.data:
            content_warning = call.data.get(ATTR_CONTENT_WARNING)
        media = None
        if ATTR_MEDIA in call.data:
            media = call.data.get(ATTR_MEDIA)
        media_warning = None
        if ATTR_MEDIA_WARNING in call.data:
            media_warning = call.data.get(ATTR_MEDIA_WARNING)

        if media:
            if not hass.config.is_allowed_path(media):
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="not_whitelisted_directory",
                    translation_placeholders={"media": media},
                )
            mediadata = await _upload_media(client, media)

            try:
                await hass.async_add_executor_job(
                    partial(
                        client.status_post,
                        status=status,
                        media_ids=mediadata["id"],
                        sensitive=content_warning,
                        visibility=visibility,
                        spoiler_text=media_warning,
                    )
                )
            except MastodonAPIError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="unable_to_send_message",
                ) from err
        else:
            try:
                await hass.async_add_executor_job(
                    partial(
                        client.status_post,
                        status=status,
                        visibility=visibility,
                        spoiler_text=content_warning,
                    )
                )
            except MastodonAPIError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="unable_to_send_message",
                ) from err
        return None

    async def _upload_media(client: Mastodon, media_path: Any = None) -> Any:
        """Upload media."""

        media_type = _media_type(media_path)
        try:
            mediadata = await hass.async_add_executor_job(
                partial(client.media_post, media_file=media_path, mime_type=media_type)
            )

        except MastodonAPIError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unable_to_upload_image",
                translation_placeholders={"media_path": media_path},
            ) from err

        return mediadata

    def _media_type(media_path: Any = None) -> Any:
        """Get media Type."""

        (media_type, _) = mimetypes.guess_type(media_path)

        return media_type

    hass.services.async_register(
        DOMAIN, SERVICE_POST, async_post, schema=SERVICE_POST_SCHEMA
    )
