"""Support for KEBA charging station notifications."""

from typing import override

from homeassistant.components.notify import NotifyEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KebaConfigEntry, KebaHandler


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KebaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the KEBA charging station notify platform."""
    keba = entry.runtime_data
    async_add_entities([KebaNotifyEntity(keba)])


class KebaNotifyEntity(NotifyEntity):
    """Notification entity for KEBA EV charger display."""

    _attr_should_poll = False

    def __init__(self, keba: KebaHandler) -> None:
        """Initialize the notify entity."""
        self._keba = keba
        self._attr_unique_id = keba.device_id
        self._attr_name = f"{keba.device_name} Display"

    @override
    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a message to the charger display."""
        text = message.replace(" ", "$")
        await self._keba.set_text(text, 2.0, 10.0)
