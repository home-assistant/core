"""Support for Tibber notifications."""

from __future__ import annotations

from homeassistant.components.notify import (
    ATTR_TITLE_DEFAULT,
    NotifyEntity,
    NotifyEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, TibberConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TibberConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Tibber notification entity."""
    async_add_entities([TibberNotificationEntity(entry)])


class TibberNotificationEntity(NotifyEntity):
    """Implement the notification entity service for Tibber."""

    _attr_supported_features = NotifyEntityFeature.TITLE
    _attr_name = DOMAIN
    _attr_icon = "mdi:message-flash"

    def __init__(self, entry: TibberConfigEntry) -> None:
        """Initialize Tibber notify entity."""
        self._attr_unique_id = entry.entry_id
        self._entry = entry

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a message to Tibber devices."""
        tibber_connection = self._entry.runtime_data.tibber_connection
        try:
            await tibber_connection.send_notification(
                title or ATTR_TITLE_DEFAULT, message
            )
        except TimeoutError as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="send_message_timeout"
            ) from exc
