"""Support for WiLight Fan."""

from __future__ import annotations

from typing import Any

from pywilight.const import (
    FAN_V1,
    ITEM_FAN,
    WL_DIRECTION_FORWARD,
    WL_DIRECTION_OFF,
    WL_DIRECTION_REVERSE,
    WL_SPEED_HIGH,
    WL_SPEED_LOW,
    WL_SPEED_MEDIUM,
)
from pywilight.wilight_device import PyWiLightDevice

from homeassistant.components.fan import DIRECTION_FORWARD, FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .const import DOMAIN
from .entity import WiLightDevice
from .parent_device import WiLightParent

ORDERED_NAMED_FAN_SPEEDS = [WL_SPEED_LOW, WL_SPEED_MEDIUM, WL_SPEED_HIGH]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up WiLight lights from a config entry."""
    parent: WiLightParent = hass.data[DOMAIN][entry.entry_id]

    # Handle a discovered WiLight device.
    entities = []
    assert parent.api
    for item in parent.api.items:
        if item["type"] != ITEM_FAN:
            continue
        index = item["index"]
        item_name = item["name"]
        if item["sub_type"] != FAN_V1:
            continue
        entities.append(WiLightFan(parent.api, index, item_name))

    async_add_entities(entities)


class WiLightFan(WiLightDevice, FanEntity):
    """Representation of a WiLights fan."""

    _attr_name = None
    _attr_speed_count = len(ORDERED_NAMED_FAN_SPEEDS)
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.DIRECTION
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )

    def __init__(self, api_device: PyWiLightDevice, index: str, item_name: str) -> None:
        """Initialize the device."""
        super().__init__(api_device, index, item_name)
        # Initialize the WiLights fan.
        self._direction = WL_DIRECTION_FORWARD

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._status.get("direction", WL_DIRECTION_OFF) != WL_DIRECTION_OFF

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if (
            "direction" in self._status
            and self._status["direction"] == WL_DIRECTION_OFF
        ):
            return 0

        if (wl_speed := self._status.get("speed")) is None:
            return None
        return ordered_list_item_to_percentage(ORDERED_NAMED_FAN_SPEEDS, wl_speed)

    @property
    def current_direction(self) -> str:
        """Return the current direction of the fan."""
        if (
            "direction" in self._status
            and self._status["direction"] != WL_DIRECTION_OFF
        ):
            self._direction = self._status["direction"]
        return self._direction

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        if percentage is None:
            await self._client.set_fan_direction(self._index, self._direction)
        else:
            await self.async_set_percentage(percentage)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan."""
        if percentage == 0:
            await self._client.set_fan_direction(self._index, WL_DIRECTION_OFF)
            return
        if (
            "direction" in self._status
            and self._status["direction"] == WL_DIRECTION_OFF
        ):
            await self._client.set_fan_direction(self._index, self._direction)
        wl_speed = percentage_to_ordered_list_item(ORDERED_NAMED_FAN_SPEEDS, percentage)
        await self._client.set_fan_speed(self._index, wl_speed)

    async def async_set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        wl_direction = WL_DIRECTION_REVERSE
        if direction == DIRECTION_FORWARD:
            wl_direction = WL_DIRECTION_FORWARD
        await self._client.set_fan_direction(self._index, wl_direction)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self._client.set_fan_direction(self._index, WL_DIRECTION_OFF)
