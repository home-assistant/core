"""Select entities for an Assist satellite entity."""

from __future__ import annotations

from abc import abstractmethod
import logging

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import restore_state

from .entity import AssistSatelliteConfiguration, AssistSatelliteWakeWord

_LOGGER = logging.getLogger(__name__)


class WakeWordSelect(SelectEntity, restore_state.RestoreEntity):
    """Entity to represent a wake word selector."""

    entity_description = SelectEntityDescription(
        key="wake_word",
        translation_key="wake_word",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_should_poll = False
    _attr_current_option: str = "Okay Nabu"
    _attr_options: list[str] = ["Okay Nabu"]

    def __init__(self, hass: HomeAssistant, unique_id_prefix: str) -> None:
        """Initialize a pipeline selector."""
        self._attr_unique_id = f"{unique_id_prefix}-wake_word"
        self.hass = hass

        # option -> wake word
        self._wake_words: dict[str, AssistSatelliteWakeWord] = {}

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state is not None:
            # Options will be updated in the background
            self._attr_options = [state.state]
            self._attr_current_option = state.state

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        if wake_word := self._wake_words.get(option):
            self.async_set_wake_word(wake_word.id)

        self._attr_current_option = option
        self.async_write_ha_state()

    @abstractmethod
    def async_set_wake_word(self, wake_word_id: str) -> None:
        """Set the selected wake word on the satellite."""

    def async_satellite_config_updated(
        self, config: AssistSatelliteConfiguration
    ) -> None:
        """Update options with available wake words."""
        if not config.available_wake_words:
            self._wake_words.clear()
            return

        self._wake_words = {w.wake_word: w for w in config.available_wake_words}
        self._attr_options = sorted(self._wake_words)

        if self._attr_current_option not in self._attr_options:
            if config.active_wake_words:
                # Select first active wake word
                wake_word_id = config.active_wake_words[0]
                for wake_word in config.available_wake_words:
                    if wake_word.id == wake_word_id:
                        self._attr_current_option = wake_word.wake_word
            else:
                # Select first available wake word
                self._attr_current_option = config.available_wake_words[0].wake_word

        self.async_write_ha_state()
