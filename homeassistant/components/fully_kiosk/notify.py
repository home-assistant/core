"""Support for Fully Kiosk Browser notifications."""

from __future__ import annotations

from dataclasses import dataclass

from fullykiosk import FullyKioskError

from homeassistant.components.notify import NotifyEntity, NotifyEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FullyKioskConfigEntry
from .coordinator import FullyKioskDataUpdateCoordinator
from .entity import FullyKioskEntity


@dataclass(frozen=True, kw_only=True)
class FullyNotifyEntityDescription(NotifyEntityDescription):
    """Fully Kiosk Browser notify entity description."""

    cmd: str


NOTIFIERS: tuple[FullyNotifyEntityDescription, ...] = (
    FullyNotifyEntityDescription(
        key="overlay_message",
        translation_key="overlay_message",
        cmd="setOverlayMessage",
    ),
    FullyNotifyEntityDescription(
        key="tts",
        translation_key="tts",
        cmd="textToSpeech",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FullyKioskConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Fully Kiosk Browser notify entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        FullyNotifyEntity(coordinator, description) for description in NOTIFIERS
    )


class FullyNotifyEntity(FullyKioskEntity, NotifyEntity):
    """Implement the notify entity for Fully Kiosk Browser."""

    entity_description: FullyNotifyEntityDescription

    def __init__(
        self,
        coordinator: FullyKioskDataUpdateCoordinator,
        description: FullyNotifyEntityDescription,
    ) -> None:
        """Initialize the entity."""
        FullyKioskEntity.__init__(self, coordinator)
        NotifyEntity.__init__(self)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data['deviceID']}-{description.key}"

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a message."""
        try:
            await self.coordinator.fully.sendCommand(
                self.entity_description.cmd, text=message
            )
        except FullyKioskError as err:
            raise HomeAssistantError(err) from err
