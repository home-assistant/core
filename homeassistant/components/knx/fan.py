"""Support for KNX/IP fans."""
import math

from xknx.devices import Fan as XknxFan, FanSpeedMode
from homeassistant.util.percentage import (
    ranged_value_to_percentage,
    percentage_to_ranged_value,
)

from typing import TYPE_CHECKING, Any, Iterator, Optional

from homeassistant.components.fan import FanEntity, SUPPORT_SET_SPEED, SUPPORT_OSCILLATE

from .const import DOMAIN
from .schema import FanSchema
from .knx_entity import KnxEntity


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
            self._step_range = (1, device.max_step or 255)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        if self._device.mode == FanSpeedMode.Step:
            step = math.ceil(percentage_to_ranged_value(self._step_range, percentage))
            self._device.set_speed(step)
        else:
            self._device.set_speed(percentage)

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        flags = 0
        if self._device.supports_oscillation:
            flags |= SUPPORT_OSCILLATE

        flags |= SUPPORT_SET_SPEED
        return flags

    @property
    def percentage(self) -> Optional[int]:
        """Return the current speed as a percentage."""
        if self._device.mode == FanSpeedMode.Step:
            percentage = ranged_value_to_percentage(
                self._step_range, self._device.speed
            )
        else:
            percentage = self._device.speed
        return percentage

    async def async_turn_on(
        self,
        speed: Optional[str] = None,
        percentage: Optional[int] = None,
        preset_mode: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Turn on the fan."""
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