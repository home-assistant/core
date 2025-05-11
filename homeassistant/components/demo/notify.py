"""Demo notification entity."""

from __future__ import annotations

from typing import Any

from homeassistant.components.notify import (
    DOMAIN as NOTIFY_DOMAIN,
    NotifyEntity,
    NotifyEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

EVENT_NOTIFY = "notify"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the demo entity platform."""
    async_add_entities([DemoNotifyEntity(unique_id="notify", device_name="Notifier")])


class DemoNotifyEntity(NotifyEntity):
    """Implement demo notification platform."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        unique_id: str,
        device_name: str,
    ) -> None:
        """Initialize the Demo button entity."""
        self._attr_unique_id = unique_id
        self._attr_supported_features = NotifyEntityFeature.TITLE
        self._attr_device_info = DeviceInfo(
            identifiers={(NOTIFY_DOMAIN, unique_id)},
            name=device_name,
        )

    async def async_send_message(
        self,
        message: str,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Send a message to a user."""
        event_notification = {"message": message}
        if title is not None:
            event_notification["title"] = title
        self.hass.bus.async_fire(EVENT_NOTIFY, event_notification)
