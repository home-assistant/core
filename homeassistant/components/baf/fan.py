"""Support for Big Ass Fans fan."""
from __future__ import annotations

import math
from typing import Any

from aiobafi6 import Device, OffOnAuto

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

from .const import DOMAIN, PRESET_MODE_WHOOSH, SPEED_COUNT, SPEED_RANGE
from .entity import BAFEntity
from .models import BAFData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SenseME fans."""
    data: BAFData = hass.data[DOMAIN][entry.entry_id]
    device = data.device
    if device.has_fan:
        async_add_entities([BAFFan(device)])


class BAFFan(BAFEntity, FanEntity):
    """BAF ceiling fan component."""

    _attr_supported_features = FanEntityFeature.SET_SPEED | FanEntityFeature.DIRECTION
    _attr_preset_modes = [PRESET_MODE_WHOOSH]

    def __init__(self, device: Device) -> None:
        """Initialize the entity."""
        super().__init__(device, device.name)
        self._attr_speed_count = SPEED_COUNT

    @callback
    def _async_update_attrs(self) -> None:
        """Update attrs from device."""
        device = self._device
        self._attr_is_on = device.fan_mode != OffOnAuto.OFF
        self._attr_current_direction = DIRECTION_FORWARD
        if device.reverse_enable:
            self._attr_current_direction = DIRECTION_REVERSE
        if self._device.speed is not None:
            self._attr_percentage = ranged_value_to_percentage(
                SPEED_RANGE, self._device.speed
            )
        else:
            self._attr_percentage = None
        whoosh = self._device.whoosh_enable
        self._attr_preset_mode = PRESET_MODE_WHOOSH if whoosh else None
        super()._async_update_attrs()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        self._device.speed = math.ceil(
            percentage_to_ranged_value(SPEED_RANGE, percentage)
        )

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on with a percentage or preset mode."""
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
        elif percentage is None:
            self._device.fan_mode = OffOnAuto.ON
        else:
            await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        self._device.fan_mode = OffOnAuto.OFF

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        if preset_mode != PRESET_MODE_WHOOSH:
            raise ValueError(f"Invalid preset mode: {preset_mode}")
        self._device.whoosh_enable = True

    async def async_set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        if direction == DIRECTION_FORWARD:
            self._device.reverse_enable = False
        else:
            self._device.reverse_enable = True
