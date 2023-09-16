"""Support for Big Ass Fans fan."""
from __future__ import annotations

import math
from typing import Any

from aiobafi6 import OffOnAuto

from homeassistant import config_entries
from homeassistant.components.fan import (
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    FanEntity,
    FanEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import DOMAIN, PRESET_MODE_AUTO, SPEED_COUNT, SPEED_RANGE
from .entity import BAFEntity
from .models import BAFData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SenseME fans."""
    data: BAFData = hass.data[DOMAIN][entry.entry_id]
    if data.device.has_fan:
        async_add_entities([BAFFan(data.device)])


class BAFFan(BAFEntity, FanEntity):
    """BAF ceiling fan component."""

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.DIRECTION
        | FanEntityFeature.PRESET_MODE
    )
    _attr_preset_modes = [PRESET_MODE_AUTO]
    _attr_speed_count = SPEED_COUNT
    _attr_name = None

    @callback
    def _async_update_attrs(self) -> None:
        """Update attrs from device."""
        self._attr_is_on = self._device.fan_mode == OffOnAuto.ON
        self._attr_current_direction = DIRECTION_FORWARD
        if self._device.reverse_enable:
            self._attr_current_direction = DIRECTION_REVERSE
        if self._device.speed is not None:
            self._attr_percentage = ranged_value_to_percentage(
                SPEED_RANGE, self._device.speed
            )
        else:
            self._attr_percentage = None
        auto = self._device.fan_mode == OffOnAuto.AUTO
        self._attr_preset_mode = PRESET_MODE_AUTO if auto else None
        super()._async_update_attrs()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        device = self._device
        if device.fan_mode != OffOnAuto.ON:
            device.fan_mode = OffOnAuto.ON
        device.speed = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on with a percentage or preset mode."""
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
            return
        if percentage is None:
            self._device.fan_mode = OffOnAuto.ON
            return
        await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        self._device.fan_mode = OffOnAuto.OFF

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        if preset_mode != PRESET_MODE_AUTO:
            raise ValueError(f"Invalid preset mode: {preset_mode}")
        self._device.fan_mode = OffOnAuto.AUTO

    async def async_set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        self._device.reverse_enable = direction == DIRECTION_REVERSE
