"""Support for Tibber notifications."""

from __future__ import annotations

from tibber import Tibber

from homeassistant.components.notify import (
    ATTR_TITLE_DEFAULT,
    NotifyEntity,
    NotifyEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN as TIBBER_DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Tibber notification entity."""
    async_add_entities([TibberNotificationEntity(entry.entry_id)])


class TibberNotificationEntity(NotifyEntity):
    """Implement the notification entity service for Tibber."""

    _attr_supported_features = NotifyEntityFeature.TITLE
    _attr_name = TIBBER_DOMAIN
    _attr_icon = "mdi:message-flash"

    def __init__(self, unique_id: str) -> None:
        """Initialize Tibber notify entity."""
        self._attr_unique_id = unique_id

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a message to Tibber devices."""
        tibber_connection: Tibber = self.hass.data[TIBBER_DOMAIN]
        try:
            await tibber_connection.send_notification(
                title or ATTR_TITLE_DEFAULT, message
            )
        except TimeoutError as exc:
            raise HomeAssistantError(
                translation_domain=TIBBER_DOMAIN, translation_key="send_message_timeout"
            ) from exc
