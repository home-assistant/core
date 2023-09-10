"""Support for WiLight lights."""
from __future__ import annotations

from typing import Any

from pywilight.const import ITEM_LIGHT, LIGHT_COLOR, LIGHT_DIMMER, LIGHT_ON_OFF
from pywilight.wilight_device import PyWiLightDevice

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, WiLightDevice
from .parent_device import WiLightParent


def entities_from_discovered_wilight(api_device: PyWiLightDevice) -> list[LightEntity]:
    """Parse configuration and add WiLight light entities."""
    entities: list[LightEntity] = []
    for item in api_device.items:
        if item["type"] != ITEM_LIGHT:
            continue
        index = item["index"]
        item_name = item["name"]
        if item["sub_type"] == LIGHT_ON_OFF:
            entities.append(WiLightLightOnOff(api_device, index, item_name))
        elif item["sub_type"] == LIGHT_DIMMER:
            entities.append(WiLightLightDimmer(api_device, index, item_name))
        elif item["sub_type"] == LIGHT_COLOR:
            entities.append(WiLightLightColor(api_device, index, item_name))

    return entities


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up WiLight lights from a config entry."""
    parent: WiLightParent = hass.data[DOMAIN][entry.entry_id]

    # Handle a discovered WiLight device.
    assert parent.api
    entities = entities_from_discovered_wilight(parent.api)
    async_add_entities(entities)


class WiLightLightOnOff(WiLightDevice, LightEntity):
    """Representation of a WiLights light on-off."""

    _attr_name = None
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    @property
    def is_on(self) -> bool | None:
        """Return true if device is on."""
        return self._status.get("on")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self._client.turn_on(self._index)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self._client.turn_off(self._index)


class WiLightLightDimmer(WiLightDevice, LightEntity):
    """Representation of a WiLights light dimmer."""

    _attr_name = None
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return int(self._status.get("brightness", 0))

    @property
    def is_on(self) -> bool | None:
        """Return true if device is on."""
        return self._status.get("on")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on,set brightness if needed."""
        # Dimmer switches use a range of [0, 255] to control
        # brightness. Level 255 might mean to set it to previous value
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            await self._client.set_brightness(self._index, brightness)
        else:
            await self._client.turn_on(self._index)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self._client.turn_off(self._index)


def wilight_to_hass_hue(value: int) -> float:
    """Convert wilight hue 1..255 to hass 0..360 scale."""
    return min(360, round((value * 360) / 255, 3))


def hass_to_wilight_hue(value: float) -> int:
    """Convert hass hue 0..360 to wilight 1..255 scale."""
    return min(255, round((value * 255) / 360))


def wilight_to_hass_saturation(value: int) -> float:
    """Convert wilight saturation 1..255 to hass 0..100 scale."""
    return min(100, round((value * 100) / 255, 3))


def hass_to_wilight_saturation(value: float) -> int:
    """Convert hass saturation 0..100 to wilight 1..255 scale."""
    return min(255, round((value * 255) / 100))


class WiLightLightColor(WiLightDevice, LightEntity):
    """Representation of a WiLights light rgb."""

    _attr_name = None
    _attr_color_mode = ColorMode.HS
    _attr_supported_color_modes = {ColorMode.HS}

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return int(self._status.get("brightness", 0))

    @property
    def hs_color(self) -> tuple[float, float]:
        """Return the hue and saturation color value [float, float]."""
        return (
            wilight_to_hass_hue(int(self._status.get("hue", 0))),
            wilight_to_hass_saturation(int(self._status.get("saturation", 0))),
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if device is on."""
        return self._status.get("on")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on,set brightness if needed."""
        # Brightness use a range of [0, 255] to control
        # Hue use a range of [0, 360] to control
        # Saturation use a range of [0, 100] to control
        if ATTR_BRIGHTNESS in kwargs and ATTR_HS_COLOR in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            hue = hass_to_wilight_hue(kwargs[ATTR_HS_COLOR][0])
            saturation = hass_to_wilight_saturation(kwargs[ATTR_HS_COLOR][1])
            await self._client.set_hsb_color(self._index, hue, saturation, brightness)
        elif ATTR_BRIGHTNESS in kwargs and ATTR_HS_COLOR not in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            await self._client.set_brightness(self._index, brightness)
        elif ATTR_BRIGHTNESS not in kwargs and ATTR_HS_COLOR in kwargs:
            hue = hass_to_wilight_hue(kwargs[ATTR_HS_COLOR][0])
            saturation = hass_to_wilight_saturation(kwargs[ATTR_HS_COLOR][1])
            await self._client.set_hs_color(self._index, hue, saturation)
        else:
            await self._client.turn_on(self._index)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self._client.turn_off(self._index)
