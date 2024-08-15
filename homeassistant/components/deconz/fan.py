"""Support for deCONZ fans."""

from __future__ import annotations

from typing import Any

from pydeconz.models.event import EventType
from pydeconz.models.light.light import Light, LightFanSpeed

from homeassistant.components.fan import DOMAIN, FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .deconz_device import DeconzDevice
from .hub import DeconzHub

ORDERED_NAMED_FAN_SPEEDS: list[LightFanSpeed] = [
    LightFanSpeed.PERCENT_25,
    LightFanSpeed.PERCENT_50,
    LightFanSpeed.PERCENT_75,
    LightFanSpeed.PERCENT_100,
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up fans for deCONZ component."""
    hub = DeconzHub.get_hub(hass, config_entry)
    hub.entities[DOMAIN] = set()

    @callback
    def async_add_fan(_: EventType, fan_id: str) -> None:
        """Add fan from deCONZ."""
        fan = hub.api.lights.lights[fan_id]
        if not fan.supports_fan_speed:
            return
        async_add_entities([DeconzFan(fan, hub)])

    hub.register_platform_add_device_callback(
        async_add_fan,
        hub.api.lights.lights,
    )


class DeconzFan(DeconzDevice[Light], FanEntity):
    """Representation of a deCONZ fan."""

    TYPE = DOMAIN
    _default_on_speed = LightFanSpeed.PERCENT_50

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, device: Light, hub: DeconzHub) -> None:
        """Set up fan."""
        super().__init__(device, hub)
        if device.fan_speed in ORDERED_NAMED_FAN_SPEEDS:
            self._default_on_speed = device.fan_speed

    @property
    def is_on(self) -> bool:
        """Return true if fan is on."""
        return self._device.fan_speed != LightFanSpeed.OFF

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if self._device.fan_speed == LightFanSpeed.OFF:
            return 0
        if self._device.fan_speed not in ORDERED_NAMED_FAN_SPEEDS:
            return None
        return ordered_list_item_to_percentage(
            ORDERED_NAMED_FAN_SPEEDS, self._device.fan_speed
        )

    @callback
    def async_update_callback(self) -> None:
        """Store latest configured speed from the device."""
        if self._device.fan_speed in ORDERED_NAMED_FAN_SPEEDS:
            self._default_on_speed = self._device.fan_speed
        super().async_update_callback()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            await self.async_turn_off()
            return
        await self.hub.api.lights.lights.set_state(
            id=self._device.resource_id,
            fan_speed=percentage_to_ordered_list_item(
                ORDERED_NAMED_FAN_SPEEDS, percentage
            ),
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
        await self.hub.api.lights.lights.set_state(
            id=self._device.resource_id,
            fan_speed=self._default_on_speed,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off fan."""
        await self.hub.api.lights.lights.set_state(
            id=self._device.resource_id,
            fan_speed=LightFanSpeed.OFF,
        )
