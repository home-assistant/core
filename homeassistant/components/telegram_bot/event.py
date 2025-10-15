"""Event platform for Telegram bot integration."""

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .bot import TelegramBotConfigEntry
from .const import (
    EVENT_TELEGRAM_CALLBACK,
    EVENT_TELEGRAM_COMMAND,
    EVENT_TELEGRAM_SENT,
    EVENT_TELEGRAM_TEXT,
)
from .entity import TelegramBotEntity


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
        EVENT_TELEGRAM_CALLBACK,
        EVENT_TELEGRAM_COMMAND,
        EVENT_TELEGRAM_TEXT,
        EVENT_TELEGRAM_SENT,
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

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        for event_type in self._attr_event_types:
            self.async_on_remove(
                self.hass.bus.async_listen(event_type, self._async_handle_event)
            )

    @callback
    def _async_handle_event(self, _: Event) -> None:
        """Handle the event."""
        self._trigger_event(str(_.event_type), dict(_.data))
        self.async_write_ha_state()
