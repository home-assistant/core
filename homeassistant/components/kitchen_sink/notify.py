"""Demo platform that offers a fake notify entity."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.components.notify import NotifyEntity, NotifyEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the demo notify entity platform."""
    async_add_entities(
        [
            DemoNotify(
                unique_id="smtp_relay_service_001",
                device_name="SMTP Relay",
                entity_name="SMTP notifier",
                supported_features=NotifyEntityFeature.MESSAGE
                | NotifyEntityFeature.TITLE,
            ),
            DemoNotify(
                unique_id="sms_service_012",
                device_name="SMS gateway",
                entity_name="SMS notifier",
                supported_features=NotifyEntityFeature.MESSAGE
                | NotifyEntityFeature.RECIPIENTS,
            ),
            DemoNotify(
                unique_id="just_notify_me",
                device_name="MyBox",
                entity_name="Personal notifier",
                supported_features=NotifyEntityFeature(0),
            ),
            DemoNotify(
                unique_id="notify_with_data",
                device_name="MyMessage",
                entity_name="Send data now",
                supported_features=NotifyEntityFeature.DATA,
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
        supported_features: NotifyEntityFeature,
    ) -> None:
        """Initialize the Demo button entity."""
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=device_name,
        )
        self._attr_name = entity_name
        self._attr_supported_features = supported_features

    def send_message(
        self,
        message: str | None = None,
        title: str | None = None,
        recipients: list[str] | None = None,
        data: Mapping[str, Any] | None = None,
    ) -> None:
        """Send out a persistent notification."""
        status_update = (
            f"Name: {self.name}, Message: {message}, Title: {title}, "
            f"Recipients: {recipients}, Data: {data}"
        )
        persistent_notification.async_create(
            self.hass, status_update, "Demo notification"
        )

    async def async_internal_added_to_hass(self) -> None:
        """Send a message after the entity has been added."""

        def _send_message():
            self.send_message("Demo message", title="Message from SMTP notifier")

        await super().async_internal_added_to_hass()
        self.hass.loop.call_soon_threadsafe(_send_message)
