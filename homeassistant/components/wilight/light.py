"""Support for WiLight lights."""

from pywilight.const import (
    DOMAIN,
    ITEM_LIGHT,
    LIGHT_COLOR,
    LIGHT_DIMMER,
    LIGHT_ON_OFF,
    SUPPORT_NONE,
)

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import WiLightDevice


def entities_from_discovered_wilight(hass, api_device):
    """Parse configuration and add WiLight light entities."""
    entities = []
    for item in api_device.items:
        if item["type"] != ITEM_LIGHT:
            continue
        index = item["index"]
        item_name = item["name"]
        if item["sub_type"] == LIGHT_ON_OFF:
            entity = WiLightLightOnOff(api_device, index, item_name)
        elif item["sub_type"] == LIGHT_DIMMER:
            entity = WiLightLightDimmer(api_device, index, item_name)
        elif item["sub_type"] == LIGHT_COLOR:
            entity = WiLightLightColor(api_device, index, item_name)
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


class WiLightLightOnOff(WiLightDevice, LightEntity):
    """Representation of a WiLights light on-off."""

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_NONE

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._status.get("on")

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self._client.turn_on(self._index)

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self._client.turn_off(self._index)


class WiLightLightDimmer(WiLightDevice, LightEntity):
    """Representation of a WiLights light dimmer."""

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return int(self._status.get("brightness", 0))

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._status.get("on")

    async def async_turn_on(self, **kwargs):
        """Turn the device on,set brightness if needed."""
        # Dimmer switches use a range of [0, 255] to control
        # brightness. Level 255 might mean to set it to previous value
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            await self._client.set_brightness(self._index, brightness)
        else:
            await self._client.turn_on(self._index)

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self._client.turn_off(self._index)


def wilight_to_hass_hue(value):
    """Convert wilight hue 1..255 to hass 0..360 scale."""
    return min(360, round((value * 360) / 255, 3))


def hass_to_wilight_hue(value):
    """Convert hass hue 0..360 to wilight 1..255 scale."""
    return min(255, round((value * 255) / 360))


def wilight_to_hass_saturation(value):
    """Convert wilight saturation 1..255 to hass 0..100 scale."""
    return min(100, round((value * 100) / 255, 3))


def hass_to_wilight_saturation(value):
    """Convert hass saturation 0..100 to wilight 1..255 scale."""
    return min(255, round((value * 255) / 100))


class WiLightLightColor(WiLightDevice, LightEntity):
    """Representation of a WiLights light rgb."""

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS | SUPPORT_COLOR

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return int(self._status.get("brightness", 0))

    @property
    def hs_color(self):
        """Return the hue and saturation color value [float, float]."""
        return [
            wilight_to_hass_hue(int(self._status.get("hue", 0))),
            wilight_to_hass_saturation(int(self._status.get("saturation", 0))),
        ]

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._status.get("on")

    async def async_turn_on(self, **kwargs):
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

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self._client.turn_off(self._index)
