"""Event platform for Telegram bot integration."""

from typing import Any, override

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .bot import TelegramBotConfigEntry
from .const import TelegramBotEvent
from .entity import TelegramBotEntity
from .helpers import signal


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TelegramBotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the event platform."""
    async_add_entities([TelegramBotEventEntity(config_entry)])


class TelegramBotEventEntity(TelegramBotEntity, EventEntity):
    """An event entity."""

    _attr_event_types = [
        TelegramBotEvent.ATTACHMENT,
        TelegramBotEvent.CALLBACK,
        TelegramBotEvent.COMMAND,
        TelegramBotEvent.TEXT,
        TelegramBotEvent.SENT,
    ]

    def __init__(
        self,
        config_entry: TelegramBotConfigEntry,
    ) -> None:
        """Initialize the entity."""

        super().__init__(
            config_entry,
            EventEntityDescription(key="update_event", translation_key="update_event"),
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                signal(self.config_entry.runtime_data.bot),
                self._async_handle_event,
            )
        )

    @callback
    def _async_handle_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Handle the event."""
        self._trigger_event(event_type, event_data)
        self.async_write_ha_state()
