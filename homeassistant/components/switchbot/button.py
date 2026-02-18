"""Button support for SwitchBot devices."""

import logging

import switchbot

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

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

    if isinstance(coordinator.device, switchbot.SwitchbotMeterProCO2):
        async_add_entities([SwitchBotMeterProCO2SyncDateTimeButton(coordinator)])


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


class SwitchBotMeterProCO2SyncDateTimeButton(SwitchbotEntity, ButtonEntity):
    """Button to sync date and time on Meter Pro CO2 to the current HA instance datetime."""

    _device: switchbot.SwitchbotMeterProCO2
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "sync_datetime"

    def __init__(self, coordinator: SwitchbotDataUpdateCoordinator) -> None:
        """Initialize the sync time button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.base_unique_id}_sync_datetime"

    @exception_handler
    async def async_press(self) -> None:
        """Sync time with Home Assistant."""
        now = dt_util.now()

        # Get UTC offset components
        utc_offset = now.utcoffset()
        utc_offset_hours, utc_offset_minutes = 0, 0
        if utc_offset is not None:
            total_seconds = int(utc_offset.total_seconds())
            utc_offset_hours = total_seconds // 3600
            utc_offset_minutes = abs(total_seconds % 3600) // 60

        timestamp = int(now.timestamp())

        _LOGGER.debug(
            "Syncing time for %s: timestamp=%s, utc_offset_hours=%s, utc_offset_minutes=%s",
            self._address,
            timestamp,
            utc_offset_hours,
            utc_offset_minutes,
        )

        await self._device.set_datetime(
            timestamp=timestamp,
            utc_offset_hours=utc_offset_hours,
            utc_offset_minutes=utc_offset_minutes,
        )
