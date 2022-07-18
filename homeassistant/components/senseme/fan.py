"""Support for Big Ass Fans SenseME fan."""
from __future__ import annotations

import math
from typing import Any

from aiosenseme import SensemeFan

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

from .const import (
    DOMAIN,
    PRESET_MODE_WHOOSH,
    SENSEME_DIRECTION_FORWARD,
    SENSEME_DIRECTION_REVERSE,
)
from .entity import SensemeEntity

SENSEME_DIRECTION_TO_HASS = {
    SENSEME_DIRECTION_FORWARD: DIRECTION_FORWARD,
    SENSEME_DIRECTION_REVERSE: DIRECTION_REVERSE,
}
HASS_DIRECTION_TO_SENSEME = {v: k for k, v in SENSEME_DIRECTION_TO_HASS.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SenseME fans."""
    device = hass.data[DOMAIN][entry.entry_id]
    if device.is_fan:
        async_add_entities([HASensemeFan(device)])


class HASensemeFan(SensemeEntity, FanEntity):
    """SenseME ceiling fan component."""

    _attr_supported_features = FanEntityFeature.SET_SPEED | FanEntityFeature.DIRECTION
    _attr_preset_modes = [PRESET_MODE_WHOOSH]

    def __init__(self, device: SensemeFan) -> None:
        """Initialize the entity."""
        super().__init__(device, device.name)
        self._attr_speed_count = self._device.fan_speed_max
        self._attr_unique_id = f"{self._device.uuid}-FAN"  # for legacy compat

    @callback
    def _async_update_attrs(self) -> None:
        """Update attrs from device."""
        self._attr_is_on = self._device.fan_on
        self._attr_current_direction = SENSEME_DIRECTION_TO_HASS.get(
            self._device.fan_dir, DIRECTION_FORWARD  # None also means forward
        )
        if self._device.fan_speed is not None:
            self._attr_percentage = ranged_value_to_percentage(
                self._device.fan_speed_limits, self._device.fan_speed
            )
        else:
            self._attr_percentage = None
        whoosh = self._device.fan_whoosh_mode
        self._attr_preset_mode = PRESET_MODE_WHOOSH if whoosh else None
        super()._async_update_attrs()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        self._device.fan_speed = math.ceil(
            percentage_to_ranged_value(self._device.fan_speed_limits, percentage)
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
            self._device.fan_on = True
        else:
            await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        self._device.fan_on = False

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        if preset_mode != PRESET_MODE_WHOOSH:
            raise ValueError(f"Invalid preset mode: {preset_mode}")
        # Sleep mode must be off for Whoosh to work.
        if self._device.sleep_mode:
            self._device.sleep_mode = False
        self._device.fan_whoosh_mode = True

    async def async_set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        self._device.fan_dir = HASS_DIRECTION_TO_SENSEME[direction]
