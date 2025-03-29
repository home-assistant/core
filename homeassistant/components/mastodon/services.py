"""Define services for the Mastodon integration."""

from enum import StrEnum
from functools import partial
from typing import Any, cast

from mastodon import Mastodon
from mastodon.Mastodon import MastodonAPIError, MediaAttachment
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_CONTENT_WARNING,
    ATTR_MEDIA,
    ATTR_MEDIA_DESCRIPTION,
    ATTR_MEDIA_WARNING,
    ATTR_STATUS,
    ATTR_VISIBILITY,
    DOMAIN,
)
from .coordinator import MastodonConfigEntry
from .utils import get_media_type


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
        vol.Optional(ATTR_CONTENT_WARNING): str,
        vol.Optional(ATTR_MEDIA): str,
        vol.Optional(ATTR_MEDIA_DESCRIPTION): str,
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

        visibility: str | None = (
            StatusVisibility(call.data[ATTR_VISIBILITY])
            if ATTR_VISIBILITY in call.data
            else None
        )
        spoiler_text: str | None = call.data.get(ATTR_CONTENT_WARNING)
        media_path: str | None = call.data.get(ATTR_MEDIA)
        media_description: str | None = call.data.get(ATTR_MEDIA_DESCRIPTION)
        media_warning: str | None = call.data.get(ATTR_MEDIA_WARNING)

        await hass.async_add_executor_job(
            partial(
                _post,
                client=client,
                status=status,
                visibility=visibility,
                spoiler_text=spoiler_text,
                media_path=media_path,
                media_description=media_description,
                sensitive=media_warning,
            )
        )

        return None

    def _post(client: Mastodon, **kwargs: Any) -> None:
        """Post to Mastodon."""

        media_data: MediaAttachment | None = None

        media_path = kwargs.get("media_path")
        if media_path:
            if not hass.config.is_allowed_path(media_path):
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="not_whitelisted_directory",
                    translation_placeholders={"media": media_path},
                )

            media_type = get_media_type(media_path)
            media_description = kwargs.get("media_description")
            try:
                media_data = client.media_post(
                    media_file=media_path,
                    mime_type=media_type,
                    description=media_description,
                )

            except MastodonAPIError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="unable_to_upload_image",
                    translation_placeholders={"media_path": media_path},
                ) from err

        kwargs.pop("media_path", None)
        kwargs.pop("media_description", None)

        try:
            media_ids: str | None = None
            if media_data:
                media_ids = media_data.id
            client.status_post(media_ids=media_ids, **kwargs)
        except MastodonAPIError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unable_to_send_message",
            ) from err

    hass.services.async_register(
        DOMAIN, SERVICE_POST, async_post, schema=SERVICE_POST_SCHEMA
    )
