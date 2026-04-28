"""Fan platform for the Novy Cooker Hood (calibrated speed control)."""

from __future__ import annotations

import math
from typing import Any

from homeassistant.components.fan import ATTR_PERCENTAGE, FanEntity, FanEntityFeature
from homeassistant.components.radio_frequency import async_send_command
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .commands import COMMAND_MINUS, COMMAND_PLUS, get_codes_for_code
from .const import CONF_CODE, SPEED_COUNT
from .entity import NovyCookerHoodEntity

PARALLEL_UPDATES = 1

_SPEED_RANGE = (1, SPEED_COUNT)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Novy Cooker Hood fan platform."""
    async_add_entities([NovyCookerHoodFan(config_entry)])


class NovyCookerHoodFan(NovyCookerHoodEntity, FanEntity, RestoreEntity):
    """Calibration-based fan: each change resets to off then climbs to target."""

    _attr_name = None
    _attr_speed_count = SPEED_COUNT
    _attr_supported_features = (
        FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.SET_SPEED
    )

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the fan."""
        super().__init__(entry)
        self._codes = get_codes_for_code(entry.data[CONF_CODE])
        self._level = 0
        self._attr_unique_id = entry.entry_id

    @property
    def is_on(self) -> bool:
        """Return whether the fan is currently on."""
        return self._level > 0

    @property
    def percentage(self) -> int:
        """Return the current speed as a percentage."""
        if self._level == 0:
            return 0
        return ranged_value_to_percentage(_SPEED_RANGE, self._level)

    async def async_added_to_hass(self) -> None:
        """Restore the last known speed level from the saved percentage."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is None:
            return
        last_pct = last.attributes.get(ATTR_PERCENTAGE)
        if isinstance(last_pct, (int, float)) and last_pct > 0:
            self._level = math.ceil(percentage_to_ranged_value(_SPEED_RANGE, last_pct))

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on at the requested level (default = 1)."""
        if percentage is None or percentage <= 0:
            level = 1
        else:
            level = math.ceil(percentage_to_ranged_value(_SPEED_RANGE, percentage))
        await self._async_set_level(level)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off by sending the calibration sequence to level 0."""
        await self._async_set_level(0)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the fan speed via calibration."""
        if percentage <= 0:
            await self._async_set_level(0)
            return
        level = math.ceil(percentage_to_ranged_value(_SPEED_RANGE, percentage))
        await self._async_set_level(level)

    async def async_increase_speed(self, percentage_step: int | None = None) -> None:
        """Bump speed up by N hardware levels (no recalibration)."""
        steps = self._steps_from_percentage(percentage_step)
        plus = await self._codes.async_load_command(COMMAND_PLUS)
        for _ in range(steps):
            await self._async_send(plus)
        self._level = min(SPEED_COUNT, self._level + steps)
        self.async_write_ha_state()

    async def async_decrease_speed(self, percentage_step: int | None = None) -> None:
        """Bump speed down by N hardware levels (no recalibration)."""
        steps = self._steps_from_percentage(percentage_step)
        minus = await self._codes.async_load_command(COMMAND_MINUS)
        for _ in range(steps):
            await self._async_send(minus)
        self._level = max(0, self._level - steps)
        self.async_write_ha_state()

    @staticmethod
    def _steps_from_percentage(percentage_step: int | None) -> int:
        """Convert a percentage step into a number of hardware level presses."""
        if percentage_step is None:
            return 1
        return math.ceil(percentage_step * SPEED_COUNT / 100)

    async def _async_set_level(self, level: int) -> None:
        """Reset to off with `SPEED_COUNT` minus presses, then climb to level."""
        minus = await self._codes.async_load_command(COMMAND_MINUS)
        for _ in range(SPEED_COUNT):
            await self._async_send(minus)
        if level > 0:
            plus = await self._codes.async_load_command(COMMAND_PLUS)
            for _ in range(level):
                await self._async_send(plus)
        self._level = level
        self.async_write_ha_state()

    async def _async_send(self, command: Any) -> None:
        """Send a single RF command via the configured transmitter."""
        await async_send_command(
            self.hass, self._transmitter, command, context=self._context
        )
