"""Support for Big Ass Fans SenseME fan."""
from __future__ import annotations

import math
from typing import Any

from aiosenseme import SensemeFan

from homeassistant import config_entries
from homeassistant.components.fan import (
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    SUPPORT_DIRECTION,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.const import CONF_DEVICE
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SenseME fans."""
    device = hass.data[DOMAIN][entry.entry_id][CONF_DEVICE]
    if device.is_fan:
        async_add_entities([HASensemeFan(device)])


class HASensemeFan(SensemeEntity, FanEntity):
    """SenseME ceiling fan component."""

    _attr_supported_features = SUPPORT_SET_SPEED | SUPPORT_DIRECTION
    _attr_preset_modes = [PRESET_MODE_WHOOSH]

    def __init__(self, device: SensemeFan) -> None:
        """Initialize the entity."""
        super().__init__(device, device.name)
        self._attr_speed_count = self._device.fan_speed_max
        self._attr_unique_id = f"{self._device.uuid}-FAN"  # for legacy compat
        self._async_update_attrs()

    @callback
    def _async_update_attrs(self) -> None:
        """Update attrs from device."""
        self._attr_is_on = self._device.fan_on
        if self._device.fan_dir == SENSEME_DIRECTION_FORWARD:
            self._attr_current_direction = DIRECTION_FORWARD
        else:
            self._attr_current_direction = DIRECTION_REVERSE
        self._attr_percentage = ranged_value_to_percentage(
            self._device.fan_speed_limits, self._device.fan_speed
        )
        if self._device.fan_whoosh_mode:
            self._attr_preset_mode = self._device.fan_whoosh_mode
        else:
            self._attr_preset_mode = None

    @callback
    def _async_update_from_device(self) -> None:
        """Process an update from the device."""
        self._async_update_attrs()
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict:
        """Get the current device state attributes."""
        return {
            "auto_comfort": self._device.fan_autocomfort.capitalize(),
            "smartmode": self._device.fan_smartmode.capitalize(),
            **super().extra_state_attributes,
        }

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        self._device.fan_speed = math.ceil(
            percentage_to_ranged_value(self._device.fan_speed_limits, percentage)
        )

    async def async_turn_on(
        self,
        speed: str | None = None,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on with speed control."""
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
            if preset_mode == PRESET_MODE_WHOOSH:
                self._device.sleep_mode = True
                return
        if percentage is None:
            self._device.fan_on = True
            return
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
        if direction == DIRECTION_FORWARD:
            self._device.fan_dir = SENSEME_DIRECTION_FORWARD
        else:
            self._device.fan_dir = SENSEME_DIRECTION_REVERSE
