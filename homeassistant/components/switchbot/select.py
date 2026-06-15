"""Select platform for SwitchBot."""

from dataclasses import dataclass
from datetime import timedelta
import logging

from collections.abc import Awaitable, Callable

import switchbot
from switchbot import NightLightState, SwitchbotOperationError

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SwitchbotConfigEntry, SwitchbotDataUpdateCoordinator
from .entity import SwitchbotEntity, exception_handler

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
        async_add_entities([SwitchBotMeterProCO2TimeFormatSelect(coordinator)], True)
    elif isinstance(coordinator.device, switchbot.SwitchbotStandingFan):
        async_add_entities(
            [
                SwitchBotStandingFanOscillationSelect(coordinator, desc)
                for desc in OSCILLATION_SELECT_DESCRIPTIONS
            ]
            + [SwitchBotStandingFanNightLightSelect(coordinator)]
        )


class SwitchBotMeterProCO2TimeFormatSelect(SwitchbotEntity, SelectEntity):
    """Select entity to set time display format on Meter Pro CO2."""

    _attr_should_poll = True
    _attr_entity_registry_enabled_default = False
    _device: switchbot.SwitchbotMeterProCO2
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "time_format"
    _attr_options = TIME_FORMAT_OPTIONS

    def __init__(self, coordinator: SwitchbotDataUpdateCoordinator) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.base_unique_id}_time_format"

    @exception_handler
    async def async_select_option(self, option: str) -> None:
        """Change the time display format."""
        _LOGGER.debug("Setting time format to %s for %s", option, self._address)
        is_12h_mode = option == TIME_FORMAT_12H
        await self._device.set_time_display_format(is_12h_mode)
        self._attr_current_option = option
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Fetch the latest time format from the device."""
        try:
            device_time = await self._device.get_datetime()
        except SwitchbotOperationError:
            _LOGGER.debug(
                "Failed to update time format for %s", self._address, exc_info=True
            )
            return
        self._attr_current_option = (
            TIME_FORMAT_12H if device_time["12h_mode"] else TIME_FORMAT_24H
        )


OSCILLATION_ANGLE_OPTIONS = ["30", "60", "90"]

NIGHT_LIGHT_OFF = "off"
NIGHT_LIGHT_LEVEL_1 = "level_1"
NIGHT_LIGHT_LEVEL_2 = "level_2"
NIGHT_LIGHT_OPTIONS = [NIGHT_LIGHT_OFF, NIGHT_LIGHT_LEVEL_1, NIGHT_LIGHT_LEVEL_2]
NIGHT_LIGHT_TO_STATE: dict[str, NightLightState] = {
    NIGHT_LIGHT_OFF: NightLightState.OFF,
    NIGHT_LIGHT_LEVEL_1: NightLightState.LEVEL_1,
    NIGHT_LIGHT_LEVEL_2: NightLightState.LEVEL_2,
}
NIGHT_LIGHT_FROM_STATE: dict[int, str] = {
    state.value: option for option, state in NIGHT_LIGHT_TO_STATE.items()
}


@dataclass(frozen=True, kw_only=True)
class SwitchBotOscillationSelectEntityDescription:
    """Describes a Standing Fan oscillation angle select entity."""

    translation_key: str
    unique_id_suffix: str
    setter: Callable[[switchbot.SwitchbotStandingFan, int], Awaitable[None]]


OSCILLATION_SELECT_DESCRIPTIONS: tuple[SwitchBotOscillationSelectEntityDescription, ...] = (
    SwitchBotOscillationSelectEntityDescription(
        translation_key=horizontal_oscillation_angle,
        unique_id_suffix=horizontal_oscillation_angle,
        setter=lambda device, angle: device.set_horizontal_oscillation_angle(angle),
    ),
    SwitchBotOscillationSelectEntityDescription(
        translation_key=vertical_oscillation_angle,
        unique_id_suffix=vertical_oscillation_angle,
        setter=lambda device, angle: device.set_vertical_oscillation_angle(angle),
    ),
)


class SwitchBotStandingFanOscillationSelect(SwitchbotEntity, SelectEntity):
    """Select entity for oscillation angle on Standing Fan.

    Uses assumed_state=True because the device does not report its current
    oscillation angle back to HA — state is only known after the user sets it.
    update_before_add is intentionally omitted (contrast with
    SwitchBotMeterProCO2TimeFormatSelect which polls via async_update).
    """

    _device: switchbot.SwitchbotStandingFan
    _attr_assumed_state = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = OSCILLATION_ANGLE_OPTIONS

    def __init__(
        self,
        coordinator: SwitchbotDataUpdateCoordinator,
        description: SwitchBotOscillationSelectEntityDescription,
    ) -> None:
        """Initialize the oscillation select entity."""
        super().__init__(coordinator)
        self._description = description
        self._attr_translation_key = description.translation_key
        self._attr_unique_id = f"{coordinator.base_unique_id}_{description.unique_id_suffix}"

    @exception_handler
    async def async_select_option(self, option: str) -> None:
        """Set oscillation angle."""
        await self._description.setter(self._device, int(option))
        self._attr_current_option = option
        self.async_write_ha_state()


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
    def current_option(self) -> str | None:
        """Return current night light state."""
        state = self._device.get_night_light_state()
        if state is None:
            return None
        return NIGHT_LIGHT_FROM_STATE.get(state)

    @exception_handler
    async def async_select_option(self, option: str) -> None:
        """Set night light state."""
        await self._device.set_night_light(NIGHT_LIGHT_TO_STATE[option])
        self.async_write_ha_state()
