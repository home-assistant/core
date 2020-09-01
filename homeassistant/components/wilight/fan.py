"""Support for WiLight Fan."""

from pywilight.const import DIRECTION_OFF, DOMAIN, FAN_V1, ITEM_FAN

from homeassistant.components.fan import (
    DIRECTION_FORWARD,
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SUPPORT_DIRECTION,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import WiLightDevice

SUPPORTED_SPEEDS = [SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

SUPPORTED_FEATURES = SUPPORT_SET_SPEED + SUPPORT_DIRECTION


def entities_from_discovered_wilight(hass, api_device):
    """Parse configuration and add WiLight fan entities."""
    entities = []
    for item in api_device.items:
        if item["type"] != ITEM_FAN:
            continue
        index = item["index"]
        item_name = item["name"]
        if item["sub_type"] == FAN_V1:
            entity = WiLightFan(api_device, index, item_name)
        else:
            continue
        entities.append(entity)

    return entities


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up WiLight lights from a config entry."""
    parent = hass.data[DOMAIN][entry.entry_id]

    # Handle a discovered WiLight device.
    entities = entities_from_discovered_wilight(hass, parent.api)
    async_add_entities(entities)


class WiLightFan(WiLightDevice, FanEntity):
    """Representation of a WiLights fan."""

    def __init__(self, *args, **kwargs):
        """Initialize the device."""
        WiLightDevice.__init__(self, *args, **kwargs)
        # Initialize the WiLights fan.
        self._direction = DIRECTION_FORWARD

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
        return self._status.get("direction", DIRECTION_OFF) != DIRECTION_OFF

    @property
    def speed(self) -> str:
        """Return the current speed."""
        return self._status.get("speed", SPEED_HIGH)

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return SUPPORTED_SPEEDS

    @property
    def current_direction(self) -> str:
        """Return the current direction of the fan."""
        if "direction" in self._status:
            if self._status["direction"] != DIRECTION_OFF:
                self._direction = self._status["direction"]
        return self._direction

    async def async_turn_on(self, speed: str = None, **kwargs):
        """Turn on the fan."""
        await self._client.set_fan_direction(self._index, self._direction)
        if speed is not None:
            await self.async_set_speed(speed)

    async def async_set_speed(self, speed: str):
        """Set the speed of the fan."""
        await self._client.set_fan_speed(self._index, speed)

    async def async_set_direction(self, direction: str):
        """Set the direction of the fan."""
        await self._client.set_fan_direction(self._index, direction)

    async def async_turn_off(self, **kwargs):
        """Turn the fan off."""
        await self._client.set_fan_direction(self._index, DIRECTION_OFF)
