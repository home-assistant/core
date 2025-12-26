"""Button support for SwitchBot devices."""

import logging

import switchbot

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SwitchbotConfigEntry, SwitchbotDataUpdateCoordinator
from .entity import SwitchbotEntity, exception_handler

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SwitchbotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Switchbot button platform."""
    coordinator = entry.runtime_data

    if isinstance(coordinator.device, switchbot.SwitchbotArtFrame):
        async_add_entities(
            [
                SwitchBotArtFrameNextButton(coordinator, "next_image"),
                SwitchBotArtFramePrevButton(coordinator, "previous_image"),
            ]
        )


class SwitchBotArtFrameButtonBase(SwitchbotEntity, ButtonEntity):
    """Base class for Art Frame buttons."""

    _device: switchbot.SwitchbotArtFrame

    def __init__(
        self, coordinator: SwitchbotDataUpdateCoordinator, translation_key: str
    ) -> None:
        """Initialize the button base."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.base_unique_id}_{translation_key}"
        self._attr_translation_key = translation_key


class SwitchBotArtFrameNextButton(SwitchBotArtFrameButtonBase):
    """Representation of a next image button."""

    @exception_handler
    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.debug("Pressing next image button %s", self._address)
        await self._device.next_image()


class SwitchBotArtFramePrevButton(SwitchBotArtFrameButtonBase):
    """Representation of a previous image button."""

    @exception_handler
    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.debug("Pressing previous image button %s", self._address)
        await self._device.prev_image()
