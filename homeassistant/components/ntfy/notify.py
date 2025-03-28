"""ntfy notification entity."""

from __future__ import annotations

from aiontfy import Message
from aiontfy.exceptions import NtfyException, NtfyHTTPError

from homeassistant.components.notify import (
    NotifyEntity,
    NotifyEntityDescription,
    NotifyEntityFeature,
)
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NtfyConfigEntry
from .const import CONF_TOPIC, DEFAULT_URL, DOMAIN

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NtfyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ntfy notification entity platform."""

    async_add_entities([NtfyNotifyEntity(config_entry, config_entry.data[CONF_TOPIC])])


class NtfyNotifyEntity(NotifyEntity):
    """Representation of a ntfy notification entity."""

    entity_description = NotifyEntityDescription(
        key="publish",
        translation_key="publish",
        name=None,
        has_entity_name=True,
    )

    def __init__(self, config_entry: NtfyConfigEntry, topic: str) -> None:
        """Initialize a notification entity."""

        self._attr_unique_id = f"{config_entry.entry_id}_{self.entity_description.key}"
        self._attr_supported_features = NotifyEntityFeature.TITLE
        self.device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="ntfy LLC",
            model="ntfy",
            model_id=config_entry.data[CONF_URL],
            name=topic,
            configuration_url=f"{DEFAULT_URL}/{topic}",
            identifiers={(DOMAIN, config_entry.entry_id)},
        )
        self.ntfy = config_entry.runtime_data
        self.topic = topic

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Publish a message to a topic."""
        msg = Message(topic=self.topic, message=message, title=title)
        try:
            await self.ntfy.publish(msg)
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
