"""Support for KNX/IP fans."""
import math
from typing import Any, Optional

from xknx.devices import Fan as XknxFan
from xknx.devices.fan import FanSpeedMode

from homeassistant.components.fan import SUPPORT_OSCILLATE, SUPPORT_SET_SPEED, FanEntity
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import DOMAIN
from .knx_entity import KnxEntity

DEFAULT_PERCENTAGE = 50


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up fans for KNX platform."""
    entities = []
    for device in hass.data[DOMAIN].xknx.devices:
        if isinstance(device, XknxFan):
            entities.append(KNXFan(device))
    async_add_entities(entities)


class KNXFan(KnxEntity, FanEntity):
    """Representation of a KNX fan."""

    def __init__(self, device: XknxFan):
        """Initialize of KNX fan."""
        super().__init__(device)

        if self._device.mode == FanSpeedMode.Step:
            self._step_range = (1, device.max_step)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        if self._device.mode == FanSpeedMode.Step:
            step = math.ceil(percentage_to_ranged_value(self._step_range, percentage))
            await self._device.set_speed(step)
        else:
            await self._device.set_speed(percentage)

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        flags = SUPPORT_SET_SPEED

        if self._device.supports_oscillation:
            flags |= SUPPORT_OSCILLATE

        return flags

    @property
    def percentage(self) -> Optional[int]:
        """Return the current speed as a percentage."""
        if self._device.current_speed is None:
            return None

        if self._device.mode == FanSpeedMode.Step:
            return ranged_value_to_percentage(
                self._step_range, self._device.current_speed
            )
        return self._device.current_speed

    async def async_turn_on(
        self,
        speed: Optional[str] = None,
        percentage: Optional[int] = None,
        preset_mode: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Turn on the fan."""
        if percentage is None:
            await self.async_set_percentage(DEFAULT_PERCENTAGE)
        else:
            await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self.async_set_percentage(0)

    async def async_oscillate(self, oscillating: bool) -> None:
        """Oscillate the fan."""
        await self._device.set_oscillation(oscillating)

    @property
    def oscillating(self):
        """Return whether or not the fan is currently oscillating."""
        return self._device.current_oscillation
