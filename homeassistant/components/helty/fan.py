"""Fan platform for the Helty Flow integration."""

from typing import Any

from pyhelty import FanMode

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .const import PRESET_BOOST, PRESET_FREE_COOLING, PRESET_NIGHT
from .coordinator import HeltyConfigEntry, HeltyDataUpdateCoordinator
from .entity import HeltyEntity

PARALLEL_UPDATES = 1

# Ordered list of discrete fan speeds, lowest to highest.
ORDERED_SPEEDS: list[FanMode] = [
    FanMode.LOW,
    FanMode.MEDIUM,
    FanMode.HIGH,
    FanMode.MAX,
]

PRESET_TO_MODE: dict[str, FanMode] = {
    PRESET_BOOST: FanMode.BOOST,
    PRESET_NIGHT: FanMode.NIGHT,
    PRESET_FREE_COOLING: FanMode.FREE_COOLING,
}
MODE_TO_PRESET: dict[FanMode, str] = {
    mode: preset for preset, mode in PRESET_TO_MODE.items()
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeltyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Helty fan."""
    async_add_entities([HeltyFan(entry.runtime_data)])


class HeltyFan(HeltyEntity, FanEntity):
    """The ventilation unit's fan, the device's primary feature."""

    _attr_name = None
    _attr_speed_count = len(ORDERED_SPEEDS)
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: HeltyDataUpdateCoordinator) -> None:
        """Initialize the fan."""
        super().__init__(coordinator)
        self._attr_unique_id = self._device_id
        self._attr_preset_modes = list(PRESET_TO_MODE)

    @property
    def _mode(self) -> FanMode:
        return self.coordinator.data.fan_mode

    @property
    def is_on(self) -> bool:
        """Return whether the fan is running."""
        return self._mode is not FanMode.OFF

    @property
    def percentage(self) -> int | None:
        """Return the current speed as a percentage, or None when on a preset."""
        if self._mode in ORDERED_SPEEDS:
            return ordered_list_item_to_percentage(ORDERED_SPEEDS, self._mode)
        return None

    @property
    def preset_mode(self) -> str | None:
        """Return the active preset, or None when running on a discrete speed."""
        return MODE_TO_PRESET.get(self._mode)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set a discrete fan speed from a percentage."""
        if percentage == 0:
            await self._async_set_mode(FanMode.OFF)
            return
        await self._async_set_mode(
            percentage_to_ordered_list_item(ORDERED_SPEEDS, percentage)
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set a preset mode."""
        await self._async_set_mode(PRESET_TO_MODE[preset_mode])

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on."""
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
        elif percentage is not None:
            await self.async_set_percentage(percentage)
        else:
            await self._async_set_mode(FanMode.LOW)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self._async_set_mode(FanMode.OFF)

    async def _async_set_mode(self, mode: FanMode) -> None:
        await self.coordinator.client.async_set_fan_mode(mode)
        await self.coordinator.async_request_refresh()
