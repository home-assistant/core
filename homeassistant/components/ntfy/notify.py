"""ntfy notification entity."""

from __future__ import annotations

from aiontfy import Message
from aiontfy.exceptions import (
    NtfyException,
    NtfyHTTPError,
    NtfyUnauthorizedAuthenticationError,
)

from homeassistant.components.notify import (
    NotifyEntity,
    NotifyEntityDescription,
    NotifyEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import NtfyConfigEntry
from .entity import NtfyBaseEntity

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
        msg = Message(topic=self.topic, message=message, title=title)
        try:
            await self.ntfy.publish(msg)
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
