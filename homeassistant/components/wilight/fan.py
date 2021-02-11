"""Support for WiLight Fan."""

from pywilight.const import (
    DOMAIN,
    FAN_V1,
    ITEM_FAN,
    WL_DIRECTION_FORWARD,
    WL_DIRECTION_OFF,
    WL_DIRECTION_REVERSE,
    WL_SPEED_HIGH,
    WL_SPEED_LOW,
    WL_SPEED_MEDIUM,
)

from homeassistant.components.fan import (
    DIRECTION_FORWARD,
    SUPPORT_DIRECTION,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from . import WiLightDevice

ORDERED_NAMED_FAN_SPEEDS = [WL_SPEED_LOW, WL_SPEED_MEDIUM, WL_SPEED_HIGH]

SUPPORTED_FEATURES = SUPPORT_SET_SPEED | SUPPORT_DIRECTION


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up WiLight lights from a config entry."""
    parent = hass.data[DOMAIN][entry.entry_id]

    # Handle a discovered WiLight device.
    entities = []
    for item in parent.api.items:
        if item["type"] != ITEM_FAN:
            continue
        index = item["index"]
        item_name = item["name"]
        if item["sub_type"] != FAN_V1:
            continue
        entity = WiLightFan(parent.api, index, item_name)
        entities.append(entity)

    async_add_entities(entities)


class WiLightFan(WiLightDevice, FanEntity):
    """Representation of a WiLights fan."""

    def __init__(self, api_device, index, item_name):
        """Initialize the device."""
        super().__init__(api_device, index, item_name)
        # Initialize the WiLights fan.
        self._direction = WL_DIRECTION_FORWARD

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORTED_FEATURES

    @property
    def icon(self):
        """Return the icon of device based on its type."""
        return "mdi:fan"

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._status.get("direction", WL_DIRECTION_OFF) != WL_DIRECTION_OFF

    @property
    def percentage(self) -> str:
        """Return the current speed percentage."""
        wl_speed = self._status.get("speed")
        if wl_speed is None:
            return None
        return ordered_list_item_to_percentage(ORDERED_NAMED_FAN_SPEEDS, wl_speed)

    @property
    def current_direction(self) -> str:
        """Return the current direction of the fan."""
        if "direction" in self._status:
            if self._status["direction"] != WL_DIRECTION_OFF:
                self._direction = self._status["direction"]
        return self._direction

    async def async_turn_on(
        self,
        speed: str = None,
        percentage: int = None,
        preset_mode: str = None,
        **kwargs,
    ) -> None:
        """Turn on the fan."""
        if percentage is None:
            await self._client.set_fan_direction(self._index, self._direction)
        else:
            await self.async_set_percentage(percentage)

    async def async_set_percentage(self, percentage: int):
        """Set the speed of the fan."""
        if percentage == 0:
            await self._client.set_fan_direction(self._index, WL_DIRECTION_OFF)
            return
        wl_speed = percentage_to_ordered_list_item(ORDERED_NAMED_FAN_SPEEDS, percentage)
        await self._client.set_fan_speed(self._index, wl_speed)

    async def async_set_direction(self, direction: str):
        """Set the direction of the fan."""
        wl_direction = WL_DIRECTION_REVERSE
        if direction == DIRECTION_FORWARD:
            wl_direction = WL_DIRECTION_FORWARD
        await self._client.set_fan_direction(self._index, wl_direction)

    async def async_turn_off(self, **kwargs):
        """Turn the fan off."""
        await self._client.set_fan_direction(self._index, WL_DIRECTION_OFF)
