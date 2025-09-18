"""ntfy notification entity."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import aiofiles
from aiontfy import Message
from aiontfy.exceptions import (
    NtfyException,
    NtfyHTTPError,
    NtfyUnauthorizedAuthenticationError,
)
import voluptuous as vol
from yarl import URL

from homeassistant.components import camera
from homeassistant.components.image import DATA_COMPONENT as IMAGE_DATA_COMPONENT
from homeassistant.components.media_source import async_resolve_media
from homeassistant.components.notify import (
    ATTR_MESSAGE,
    ATTR_TITLE,
    NotifyEntity,
    NotifyEntityDescription,
    NotifyEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.selector import MediaSelector

from .const import DOMAIN
from .coordinator import NtfyConfigEntry
from .entity import NtfyBaseEntity

PARALLEL_UPDATES = 0


SERVICE_PUBLISH = "publish"
ATTR_ATTACH = "attach"
ATTR_CALL = "call"
ATTR_CLICK = "click"
ATTR_DELAY = "delay"
ATTR_EMAIL = "email"
ATTR_ICON = "icon"
ATTR_MARKDOWN = "markdown"
ATTR_PRIORITY = "priority"
ATTR_TAGS = "tags"
ATTR_ATTACH_FILE = "attach_file"

SERVICE_PUBLISH_SCHEMA = cv.make_entity_service_schema(
    {
        vol.Optional(ATTR_TITLE): cv.string,
        vol.Optional(ATTR_MESSAGE): cv.string,
        vol.Optional(ATTR_MARKDOWN): cv.boolean,
        vol.Optional(ATTR_TAGS): vol.All(cv.ensure_list, [str]),
        vol.Optional(ATTR_PRIORITY): vol.All(vol.Coerce(int), vol.Range(1, 5)),
        vol.Optional(ATTR_CLICK): vol.All(vol.Url(), vol.Coerce(URL)),
        vol.Optional(ATTR_DELAY): vol.All(
            cv.time_period,
            vol.Range(min=timedelta(seconds=10), max=timedelta(days=3)),
        ),
        vol.Optional(ATTR_ATTACH): vol.All(vol.Url(), vol.Coerce(URL)),
        vol.Optional(ATTR_EMAIL): vol.Email(),
        vol.Optional(ATTR_CALL): cv.string,
        vol.Optional(ATTR_ICON): vol.All(vol.Url(), vol.Coerce(URL)),
        vol.Optional(ATTR_ATTACH_FILE): MediaSelector({"accept": ["*/*"]}),
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NtfyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the ntfy notification entity platform."""

    for subentry_id, subentry in config_entry.subentries.items():
        async_add_entities(
            [NtfyNotifyEntity(config_entry, subentry)], config_subentry_id=subentry_id
        )

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_PUBLISH,
        SERVICE_PUBLISH_SCHEMA,
        "publish",
    )


class NtfyNotifyEntity(NtfyBaseEntity, NotifyEntity):
    """Representation of a ntfy notification entity."""

    entity_description = NotifyEntityDescription(
        key="publish",
        translation_key="publish",
        name=None,
    )
    _attr_supported_features = NotifyEntityFeature.TITLE

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Publish a message to a topic."""
        await self.publish(message=message, title=title)

    async def publish(self, **kwargs: Any) -> None:
        """Publish a message to a topic."""
        attachment = None
        params: dict[str, Any] = kwargs
        delay: timedelta | None = params.get("delay")
        if delay:
            params["delay"] = f"{delay.total_seconds()}s"
            if params.get("email"):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="delay_no_email",
                )
            if params.get("call"):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="delay_no_call",
                )
        if file := params.pop(ATTR_ATTACH_FILE, None):
            if params.get(ATTR_ATTACH) is not None:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="attach_url_xor_local",
                )
            media_content_id: str = file["media_content_id"]
            if media_content_id.startswith("media-source://camera/"):
                entity_id = media_content_id.removeprefix("media-source://camera/")
                img = await camera.async_get_image(self.hass, entity_id)
                attachment = img.content
            elif media_content_id.startswith("media-source://image/"):
                entity_id = media_content_id.removeprefix("media-source://image/")
                if (
                    entity := self.hass.data[IMAGE_DATA_COMPONENT].get_entity(entity_id)
                ) is None:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="image_source_not_found",
                    )
                attachment = await entity.async_image()
            else:
                media = await async_resolve_media(
                    self.hass, file["media_content_id"], None
                )

                if media.path is None:
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key="media_source_not_supported",
                    )
                async with aiofiles.open(media.path, mode="rb") as f:
                    attachment = await f.read()
                params["filename"] = media.path.name

        msg = Message(topic=self.topic, **params)
        try:
            await self.ntfy.publish(msg, attachment)
        except NtfyUnauthorizedAuthenticationError as e:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="authentication_error",
            ) from e
        except NtfyHTTPError as e:
            raise HomeAssistantError(
                translation_key="publish_failed_request_error",
                translation_domain=DOMAIN,
                translation_placeholders={"error_msg": e.error},
            ) from e
        except NtfyException as e:
            raise HomeAssistantError(
                translation_key="publish_failed_exception",
                translation_domain=DOMAIN,
            ) from e
