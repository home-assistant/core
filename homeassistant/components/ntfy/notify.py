"""ntfy notification entity."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from aiontfy import Message
from aiontfy.exceptions import (
    NtfyException,
    NtfyHTTPError,
    NtfyUnauthorizedAuthenticationError,
)

from homeassistant.components import camera, image
from homeassistant.components.media_source import async_resolve_media
from homeassistant.components.notify import (
    NotifyEntity,
    NotifyEntityDescription,
    NotifyEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import NtfyConfigEntry
from .entity import NtfyBaseEntity
from .services import ATTR_ATTACH_FILE, ATTR_FILENAME, ATTR_SEQUENCE_ID

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


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
            media_content_id: str = file["media_content_id"]
            if media_content_id.startswith("media-source://camera/"):
                entity_id = media_content_id.removeprefix("media-source://camera/")
                attachment = (
                    await camera.async_get_image(self.hass, entity_id)
                ).content
            elif media_content_id.startswith("media-source://image/"):
                entity_id = media_content_id.removeprefix("media-source://image/")
                attachment = (await image.async_get_image(self.hass, entity_id)).content
            else:
                media = await async_resolve_media(
                    self.hass, file["media_content_id"], None
                )

                if media.path is None:
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key="media_source_not_supported",
                    )

                attachment = await self.hass.async_add_executor_job(
                    media.path.read_bytes
                )

                params.setdefault(ATTR_FILENAME, media.path.name)

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

    async def clear(self, **kwargs: Any) -> None:
        """Clear a message."""

        params: dict[str, Any] = kwargs

        try:
            await self.ntfy.clear(self.topic, params[ATTR_SEQUENCE_ID])
        except NtfyUnauthorizedAuthenticationError as e:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="authentication_error",
            ) from e
        except NtfyException as e:
            _LOGGER.debug("Exception:", exc_info=True)
            raise HomeAssistantError(
                translation_key="clear_failed",
                translation_domain=DOMAIN,
            ) from e

    async def delete(self, **kwargs: Any) -> None:
        """Delete a message."""

        params: dict[str, Any] = kwargs

        try:
            await self.ntfy.delete(self.topic, params[ATTR_SEQUENCE_ID])
        except NtfyUnauthorizedAuthenticationError as e:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="authentication_error",
            ) from e
        except NtfyException as e:
            _LOGGER.debug("Exception:", exc_info=True)
            raise HomeAssistantError(
                translation_key="delete_failed",
                translation_domain=DOMAIN,
            ) from e
