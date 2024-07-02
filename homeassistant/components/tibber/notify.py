"""Support for Tibber notifications."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from tibber import Tibber

from homeassistant.components.notify import (
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    BaseNotificationService,
    NotifyEntity,
    NotifyEntityFeature,
    migrate_notify_issue,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN as TIBBER_DOMAIN


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> TibberNotificationService:
    """Get the Tibber notification service."""
    tibber_connection: Tibber = hass.data[TIBBER_DOMAIN]
    return TibberNotificationService(tibber_connection.send_notification)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Tibber notification entity."""
    async_add_entities([TibberNotificationEntity(entry.entry_id)])


class TibberNotificationService(BaseNotificationService):
    """Implement the notification service for Tibber."""

    def __init__(self, notify: Callable) -> None:
        """Initialize the service."""
        self._notify = notify

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to Tibber devices."""
        migrate_notify_issue(
            self.hass,
            TIBBER_DOMAIN,
            "Tibber",
            "2024.12.0",
            service_name=self._service_name,
        )
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        try:
            await self._notify(title=title, message=message)
        except TimeoutError as exc:
            raise HomeAssistantError(
                translation_domain=TIBBER_DOMAIN, translation_key="send_message_timeout"
            ) from exc


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
