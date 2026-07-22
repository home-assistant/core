"""Base entity for Telegram bot integration."""

from homeassistant.helpers.entity import Entity, EntityDescription

from . import TelegramBotConfigEntry, bot_device_info


class TelegramBotEntity(Entity):
    """Base entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        config_entry: TelegramBotConfigEntry,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize the entity."""

        self.bot_id = config_entry.runtime_data.bot.id
        self.config_entry = config_entry
        self.entity_description = entity_description
        self.service = config_entry.runtime_data

        self._attr_unique_id = f"{self.bot_id}_{entity_description.key}"
        self._attr_device_info = bot_device_info(config_entry, self.bot_id)
