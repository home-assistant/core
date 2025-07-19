"""Support for Switchbot button."""

from typing import Any

import switchbot

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SwitchbotConfigEntry
from .entity import SwitchbotEntity, exception_handler

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SwitchbotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Switchbot based on a config entry."""
    async_add_entities([SwitchbotButtonEntity(entry.runtime_data)])


class SwitchbotButtonEntity(SwitchbotEntity, ButtonEntity):
    """Representation of a Switchbot button."""

    _device: switchbot.SwitchbotDevice
    _attr_translation_key = "button"
    _attr_name = None

    @exception_handler
    async def async_press(self, **kwargs: Any) -> None:
        """Handle the button press action."""
        await self._device.press()
