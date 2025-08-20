"""WiZ integration fan platform."""

from __future__ import annotations

import math
from typing import Any, ClassVar

from pywizlight.bulblibrary import BulbType, Features

from homeassistant.components.fan import (
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    FanEntity,
    FanEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from . import WizConfigEntry
from .entity import WizEntity
from .models import WizData

PRESET_MODE_BREEZE = "breeze"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WizConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the WiZ Platform from config_flow."""
    if entry.runtime_data.bulb.bulbtype.features.fan:
        async_add_entities([WizFanEntity(entry.runtime_data, entry.title)])


class WizFanEntity(WizEntity, FanEntity):
    """Representation of WiZ Light bulb."""

    _attr_name = None

    # We want the implementation of is_on to be the same as in ToggleEntity,
    # but it is being overridden in FanEntity, so we need to restore it here.
    is_on: ClassVar = ToggleEntity.is_on

    def __init__(self, wiz_data: WizData, name: str) -> None:
        """Initialize a WiZ fan."""
        super().__init__(wiz_data, name)
        bulb_type: BulbType = self._device.bulbtype
        features: Features = bulb_type.features

        supported_features = (
            FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.SET_SPEED
        )
        if features.fan_reverse:
            supported_features |= FanEntityFeature.DIRECTION
        if features.fan_breeze_mode:
            supported_features |= FanEntityFeature.PRESET_MODE
            self._attr_preset_modes = [PRESET_MODE_BREEZE]

        self._attr_supported_features = supported_features
        self._attr_speed_count = bulb_type.fan_speed_range

        self._async_update_attrs()

    @callback
    def _async_update_attrs(self) -> None:
        """Handle updating _attr values."""
        state = self._device.state

        self._attr_is_on = state.get_fan_state() > 0
        self._attr_percentage = ranged_value_to_percentage(
            (1, self.speed_count), state.get_fan_speed()
        )
        if FanEntityFeature.PRESET_MODE in self.supported_features:
            fan_mode = state.get_fan_mode()
            self._attr_preset_mode = PRESET_MODE_BREEZE if fan_mode == 2 else None
        if FanEntityFeature.DIRECTION in self.supported_features:
            fan_reverse = state.get_fan_reverse()
            self._attr_current_direction = None
            if fan_reverse == 0:
                self._attr_current_direction = DIRECTION_FORWARD
            elif fan_reverse == 1:
                self._attr_current_direction = DIRECTION_REVERSE

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        # preset_mode == PRESET_MODE_BREEZE
        await self._device.fan_set_state(mode=2)
        await self.coordinator.async_request_refresh()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            await self.async_turn_off()
            return

        speed = math.ceil(percentage_to_ranged_value((1, self.speed_count), percentage))
        await self._device.fan_set_state(mode=1, speed=speed)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        mode: int | None = None
        speed: int | None = None
        if preset_mode is not None:
            self._valid_preset_mode_or_raise(preset_mode)
            if preset_mode == PRESET_MODE_BREEZE:
                mode = 2
        if percentage is not None:
            speed = math.ceil(
                percentage_to_ranged_value((1, self.speed_count), percentage)
            )
            if mode is None:
                mode = 1
        await self._device.fan_turn_on(mode=mode, speed=speed)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        await self._device.fan_turn_off(**kwargs)
        await self.coordinator.async_request_refresh()

    async def async_set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        reverse = 1 if direction == DIRECTION_REVERSE else 0
        await self._device.fan_set_state(reverse=reverse)
        await self.coordinator.async_request_refresh()
