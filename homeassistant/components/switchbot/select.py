"""Select platform for SwitchBot."""

from datetime import timedelta
import logging
from typing import override

import switchbot
from switchbot import NightLightState

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SwitchbotConfigEntry, SwitchbotDataUpdateCoordinator
from .entity import SwitchbotConnectionPolledEntity, SwitchbotEntity, exception_handler

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0

SCAN_INTERVAL = timedelta(days=7)
TIME_FORMAT_12H = "12h"
TIME_FORMAT_24H = "24h"
TIME_FORMAT_OPTIONS = [TIME_FORMAT_12H, TIME_FORMAT_24H]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SwitchbotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SwitchBot select platform."""
    coordinator = entry.runtime_data

    if isinstance(coordinator.device, switchbot.SwitchbotMeterProCO2):
        async_add_entities([SwitchBotMeterProCO2TimeFormatSelect(coordinator)])
    elif isinstance(coordinator.device, switchbot.SwitchbotStandingFan):
        async_add_entities([SwitchBotStandingFanNightLightSelect(coordinator)])


class SwitchBotMeterProCO2TimeFormatSelect(
    SwitchbotConnectionPolledEntity, SelectEntity
):
    """Select entity to set time display format on Meter Pro CO2."""

    _device: switchbot.SwitchbotMeterProCO2
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "time_format"
    _attr_options = TIME_FORMAT_OPTIONS

    def __init__(self, coordinator: SwitchbotDataUpdateCoordinator) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.base_unique_id}_time_format"

    @exception_handler
    @override
    async def async_select_option(self, option: str) -> None:
        """Change the time display format."""
        _LOGGER.debug("Setting time format to %s for %s", option, self._address)
        is_12h_mode = option == TIME_FORMAT_12H
        await self._device.set_time_display_format(is_12h_mode)
        self._attr_current_option = option
        self.async_write_ha_state()

    @override
    async def _async_read_value(self) -> None:
        """Fetch the latest time format from the device."""
        device_time = await self._device.get_datetime()
        self._attr_current_option = (
            TIME_FORMAT_12H if device_time["12h_mode"] else TIME_FORMAT_24H
        )


NIGHT_LIGHT_OFF = "off"
NIGHT_LIGHT_BRIGHT = "bright"
NIGHT_LIGHT_SOFT = "soft"
NIGHT_LIGHT_OPTIONS = [NIGHT_LIGHT_OFF, NIGHT_LIGHT_SOFT, NIGHT_LIGHT_BRIGHT]
NIGHT_LIGHT_TO_STATE: dict[str, NightLightState] = {
    NIGHT_LIGHT_OFF: NightLightState.OFF,
    NIGHT_LIGHT_SOFT: NightLightState.LEVEL_2,
    NIGHT_LIGHT_BRIGHT: NightLightState.LEVEL_1,
}
NIGHT_LIGHT_FROM_STATE: dict[int, str] = {
    state.value: option for option, state in NIGHT_LIGHT_TO_STATE.items()
}


class SwitchBotStandingFanNightLightSelect(SwitchbotEntity, SelectEntity):
    """Select entity for night light on Standing Fan."""

    _device: switchbot.SwitchbotStandingFan
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "night_light"
    _attr_options = NIGHT_LIGHT_OPTIONS

    def __init__(self, coordinator: SwitchbotDataUpdateCoordinator) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.base_unique_id}_night_light"

    @property
    @override
    def current_option(self) -> str | None:
        """Return current night light state."""
        state = self._device.get_night_light_state()
        if state is None:
            return None
        return NIGHT_LIGHT_FROM_STATE.get(state)

    @exception_handler
    @override
    async def async_select_option(self, option: str) -> None:
        """Set night light state."""
        await self._device.set_night_light(NIGHT_LIGHT_TO_STATE[option])
        self.async_write_ha_state()
