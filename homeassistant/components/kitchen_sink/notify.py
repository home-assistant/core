"""Demo platform that offers a fake notify entity."""

from dataclasses import dataclass
from typing import override

from homeassistant.components import persistent_notification
from homeassistant.components.notify import (
    NotifyEntity,
    NotifyEntityDescription,
    NotifyEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN


@dataclass(frozen=True, kw_only=True)
class DemoNotifyEntityDescription(NotifyEntityDescription):
    """Describes a demo notify entity."""

    device_name: str
    supported_features: NotifyEntityFeature


NOTIFIERS = (
    DemoNotifyEntityDescription(
        key="just_notify_me",
        name="Personal notifier",
        device_name="MyBox",
        supported_features=NotifyEntityFeature(0),
    ),
    DemoNotifyEntityDescription(
        key="just_notify_me_title",
        name="Personal notifier with title",
        device_name="MyBox",
        supported_features=NotifyEntityFeature.TITLE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the demo notify entity platform."""
    async_add_entities(DemoNotify(description) for description in NOTIFIERS)


class DemoNotify(NotifyEntity):
    """Representation of a demo notify entity."""

    entity_description: DemoNotifyEntityDescription
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, description: DemoNotifyEntityDescription) -> None:
        """Initialize the Demo button entity."""
        self.entity_description = description
        self._attr_unique_id = description.key
        self._attr_supported_features = description.supported_features
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, description.key)},
            name=description.device_name,
        )

    @override
    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send out a persistent notification."""
        persistent_notification.async_create(
            self.hass, message, title or "Demo notification"
        )
