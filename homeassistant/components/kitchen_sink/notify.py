"""Demo platform that offers a fake notify entity."""

from __future__ import annotations

from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.components.notify import NotifyEntity, NotifyEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the demo notify entity platform."""
    async_add_entities(
        [
            DemoNotify(
                unique_id="just_notify_me",
                device_name="MyBox",
                entity_name="Personal notifier",
            ),
            DemoNotify(
                unique_id="just_notify_me_title",
                device_name="MyBox",
                entity_name="Personal notifier with title",
                supported_features=NotifyEntityFeature.TITLE,
            ),
        ]
    )


class DemoNotify(NotifyEntity):
    """Representation of a demo notify entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str,
        device_name: str,
        entity_name: str | None,
        supported_features: NotifyEntityFeature = NotifyEntityFeature(0),
    ) -> None:
        """Initialize the Demo button entity."""
        self._attr_unique_id = unique_id
        self._attr_supported_features = supported_features
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=device_name,
        )
        self._attr_name = entity_name

    async def async_send_message(
        self,
        message: str,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Send out a persistent notification."""
        persistent_notification.async_create(
            self.hass, message, title or "Demo notification"
        )
