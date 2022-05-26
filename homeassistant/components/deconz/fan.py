"""Support for deCONZ fans."""
from __future__ import annotations

from typing import Any, Literal

from pydeconz.models.event import EventType
from pydeconz.models.light.fan import (
    FAN_SPEED_25_PERCENT,
    FAN_SPEED_50_PERCENT,
    FAN_SPEED_75_PERCENT,
    FAN_SPEED_100_PERCENT,
    FAN_SPEED_OFF,
    Fan,
)

from homeassistant.components.fan import DOMAIN, FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .deconz_device import DeconzDevice
from .gateway import DeconzGateway, get_gateway_from_config_entry

ORDERED_NAMED_FAN_SPEEDS: list[Literal[0, 1, 2, 3, 4, 5, 6]] = [
    FAN_SPEED_25_PERCENT,
    FAN_SPEED_50_PERCENT,
    FAN_SPEED_75_PERCENT,
    FAN_SPEED_100_PERCENT,
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up fans for deCONZ component."""
    gateway = get_gateway_from_config_entry(hass, config_entry)
    gateway.entities[DOMAIN] = set()

    @callback
    def async_add_fan(_: EventType, fan_id: str) -> None:
        """Add fan from deCONZ."""
        fan = gateway.api.lights.fans[fan_id]
        async_add_entities([DeconzFan(fan, gateway)])

    gateway.register_platform_add_device_callback(
        async_add_fan,
        gateway.api.lights.fans,
    )


class DeconzFan(DeconzDevice, FanEntity):
    """Representation of a deCONZ fan."""

    TYPE = DOMAIN
    _device: Fan
    _default_on_speed: Literal[0, 1, 2, 3, 4, 5, 6]

    _attr_supported_features = FanEntityFeature.SET_SPEED

    def __init__(self, device: Fan, gateway: DeconzGateway) -> None:
        """Set up fan."""
        super().__init__(device, gateway)

        self._default_on_speed = FAN_SPEED_50_PERCENT
        if self._device.speed in ORDERED_NAMED_FAN_SPEEDS:
            self._default_on_speed = self._device.speed

    @property
    def is_on(self) -> bool:
        """Return true if fan is on."""
        return self._device.speed != FAN_SPEED_OFF

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if self._device.speed == FAN_SPEED_OFF:
            return 0
        if self._device.speed not in ORDERED_NAMED_FAN_SPEEDS:
            return None
        return ordered_list_item_to_percentage(
            ORDERED_NAMED_FAN_SPEEDS, self._device.speed
        )

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return len(ORDERED_NAMED_FAN_SPEEDS)

    @callback
    def async_update_callback(self) -> None:
        """Store latest configured speed from the device."""
        if self._device.speed in ORDERED_NAMED_FAN_SPEEDS:
            self._default_on_speed = self._device.speed
        super().async_update_callback()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            return await self.async_turn_off()
        await self._device.set_speed(
            percentage_to_ordered_list_item(ORDERED_NAMED_FAN_SPEEDS, percentage)
        )

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on fan."""
        if percentage is not None:
            await self.async_set_percentage(percentage)
            return
        await self._device.set_speed(self._default_on_speed)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off fan."""
        await self._device.set_speed(FAN_SPEED_OFF)
