"""Support for KNX/IP fans."""
from __future__ import annotations

import math
from typing import Any, Final

from xknx import XKNX
from xknx.devices import Fan as XknxFan

from homeassistant.components.fan import SUPPORT_OSCILLATE, SUPPORT_SET_SPEED, FanEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.percentage import (
    int_states_in_range,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import DOMAIN, KNX_ADDRESS
from .knx_entity import KnxEntity
from .schema import FanSchema

DEFAULT_PERCENTAGE: Final = 50


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up fans for KNX platform."""
    if not discovery_info or not discovery_info["platform_config"]:
        return
    platform_config = discovery_info["platform_config"]
    xknx: XKNX = hass.data[DOMAIN].xknx

    async_add_entities(KNXFan(xknx, entity_config) for entity_config in platform_config)


class KNXFan(KnxEntity, FanEntity):
    """Representation of a KNX fan."""

    _device: XknxFan

    def __init__(self, xknx: XKNX, config: ConfigType) -> None:
        """Initialize of KNX fan."""
        max_step = config.get(FanSchema.CONF_MAX_STEP)
        super().__init__(
            device=XknxFan(
                xknx,
                name=config[CONF_NAME],
                group_address_speed=config.get(KNX_ADDRESS),
                group_address_speed_state=config.get(FanSchema.CONF_STATE_ADDRESS),
                group_address_oscillation=config.get(
                    FanSchema.CONF_OSCILLATION_ADDRESS
                ),
                group_address_oscillation_state=config.get(
                    FanSchema.CONF_OSCILLATION_STATE_ADDRESS
                ),
                max_step=max_step,
            )
        )
        # FanSpeedMode.STEP if max_step is set
        self._step_range: tuple[int, int] | None = (1, max_step) if max_step else None

        self._attr_unique_id = str(self._device.speed.group_address)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        if self._step_range:
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
    def percentage(self) -> int | None:
        """Return the current speed as a percentage."""
        if self._device.current_speed is None:
            return None

        if self._step_range:
            return ranged_value_to_percentage(
                self._step_range, self._device.current_speed
            )
        return self._device.current_speed

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        if self._step_range is None:
            return super().speed_count
        return int_states_in_range(self._step_range)

    async def async_turn_on(
        self,
        speed: str | None = None,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
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
    def oscillating(self) -> bool | None:
        """Return whether or not the fan is currently oscillating."""
        return self._device.current_oscillation
