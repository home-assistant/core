"""Platform for sensor integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components import light
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_TRANSITION,
    ATTR_WHITE,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_HS,
    COLOR_MODE_ONOFF,
    COLOR_MODE_RGB,
    COLOR_MODE_RGBW,
    COLOR_MODE_RGBWW,
    COLOR_MODE_WHITE,
    SUPPORT_EFFECT,
    SUPPORT_TRANSITION,
    LightEntity,
    brightness_supported,
)
from homeassistant.core import callback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.color as color_util

from . import async_create_new_platform_entity
from .const import DOMAIN


# Handle platform
async def async_setup_entry(hass, ConfigEntry, async_add_entities):
    """Set up the Oocsi light platform."""
    # Add the corresponding oocsi server
    api = hass.data[DOMAIN][ConfigEntry.entry_id]
    platform = "light"
    # Create entities >  __init__.py
    await async_create_new_platform_entity(
        hass, ConfigEntry, api, BasicLight, async_add_entities, platform
    )


class BasicLight(LightEntity):
    # Import & configure entity
    def __init__(self, hass, entity_name, api, entityProperty):
        # Basic variables
        self._supported_color_modes: set[str] | None = None
        self._hass = hass
        self._oocsi = api
        self._name = entity_name

        # Set properties
        self._attr_unique_id = entityProperty["channelName"]
        self._oocsichannel = entityProperty["channelName"]
        self._channelState = entityProperty["state"]

        # self._supportedFeature = entityProperty["type"]
        self._brightness = entityProperty["brightness"]
        self._ledType = entityProperty["ledType"]
        self._spectrum = entityProperty["spectrum"]
        self._color_mode: str | None = None
        self._color_temp: int | None = None
        self._white_value: int | None = None
        self._supported_features = 0
        self._supported_color_modes: set[str]
        self._rgb: tuple[int, int, int] | None = None
        self._rgbw: tuple[int, int, int, int] | None = None
        self._rgbww: tuple[int, int, int, int, int] | None = None

        if entityProperty.get("effect"):
            self._attr_supported_features |= SUPPORT_EFFECT
            self._effect: str | None = None
            self._effectList = entityProperty["effect"]

    async def _color_setup(self):
        self._supported_color_modes = set()
        ledType = self._ledType

        if ledType in ["RGB", "RGBW", "RGBWW"]:
            spectrum = self._spectrum
            if "CCT" in spectrum:
                self._supported_color_modes.add(COLOR_MODE_COLOR_TEMP)
            if "RGB" in spectrum:
                if ledType == "RGBWW":
                    self._supported_color_modes.add(COLOR_MODE_RGBWW)
                    self._color_mode = COLOR_MODE_RGBWW
                if ledType == "RGBW":
                    self._supported_color_modes.add(COLOR_MODE_RGBW)
                    self._color_mode = COLOR_MODE_RGBW
                if ledType == "RGB":
                    self._supported_color_modes.add(COLOR_MODE_RGB)
                    self._color_mode = COLOR_MODE_RGB
            if "WHITE" in spectrum:
                self._supported_color_modes.add(COLOR_MODE_WHITE)
        if ledType == "WHITE":
            self._supported_color_modes.add(COLOR_MODE_WHITE)
        if ledType == "CCT":
            self._supported_color_modes.add(COLOR_MODE_COLOR_TEMP)

    async def async_added_to_hass(self) -> None:
        """Create oocsi listener"""

        @callback
        def channelUpdateEvent(sender, recipient, event, **kwargs: Any):
            """Handle oocsi event"""
            self._channelState = event["state"]
            if COLOR_MODE_RGB in self._supported_color_modes:
                self._RGB = event["colorrgb"]
            if COLOR_MODE_RGBW in self._supported_color_modes:
                self._RGBW = event["colorrgbw"]
            if COLOR_MODE_RGBWW in self._supported_color_modes:
                self._RGBWW = event["colorrgbww"]
            if brightness_supported(self._supported_color_modes):
                self._brightness = event["brightness"]
            if COLOR_MODE_COLOR_TEMP in self._supported_color_modes:
                self._color_temp = event["color_temp"]
            if COLOR_MODE_WHITE in self._supported_color_modes:
                self._white_value = event["white"]

            self.async_write_ha_state()

        await self._color_setup()
        self._oocsi.subscribe(self._oocsichannel, channelUpdateEvent)

    @property
    def color_mode(self) -> str | None:
        """Return the color mode of the light."""
        return self._color_mode

    @property
    def color_temp(self) -> int | None:
        """Return the color temperature in mired."""
        return self._color_temp

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the hs color value."""
        if self._rgb is None:
            return None
        rgb_color = self._rgb
        return (rgb_color[0], rgb_color[1], rgb_color[2])

    @property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Return the hs color value."""
        if self._rgbw is None:
            return None
        rgbw_color = self._rgbw
        return (rgbw_color[0], rgbw_color[1], rgbw_color[2], rgbw_color[3])

    @property
    def rgbww_color(self) -> tuple[int, int, int, int, int] | None:
        """Return the hs color value."""
        if self._rgbww is None:
            return None
        rgbww_color = self._rgbww
        return (
            rgbww_color[0],
            rgbww_color[1],
            rgbww_color[2],
            rgbww_color[3],
            rgbww_color[4],
        )

    @property
    def supported_color_modes(self) -> set[str] | None:
        """Flag supported color modes."""
        return self._supported_color_modes

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def device_info(self):
        return {"name": self._name}

    @property
    def icon(self) -> str:
        """Return the icon."""
        # return self._static_info.icon
        return "mdi:toggle-switch"

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        return self._effect

    @property
    def effect_list(self) -> list[str] | None:
        """Return the list of supported effects."""
        return self._effectList

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._supported_features

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return self._channelState

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self._channelState = True
        self._oocsi.send(self._oocsichannel, {"state": True})
        supported_color_modes = self._supported_color_modes

        if ATTR_RGB_COLOR in kwargs and COLOR_MODE_RGB in supported_color_modes:
            self._color_mode = COLOR_MODE_RGB
            rgb_color = kwargs.get(ATTR_RGB_COLOR)
            self._rgb = rgb_color
            self._color_temp = None
            self._oocsi.send(self._oocsichannel, {"colorrgb": rgb_color})

        if ATTR_RGBW_COLOR in kwargs and COLOR_MODE_RGBW in supported_color_modes:
            self._color_mode = COLOR_MODE_RGBW
            rgbw_color = kwargs.get(ATTR_RGBW_COLOR)
            self._rgbw = rgbw_color
            self._color_temp = None
            self._oocsi.send(self._oocsichannel, {"colorrgbw": rgbw_color})

        if ATTR_RGBWW_COLOR in kwargs and COLOR_MODE_RGBWW in supported_color_modes:
            self._color_mode = COLOR_MODE_RGBWW
            rgbww_color = kwargs.get(ATTR_RGBWW_COLOR)
            self._rgbww = rgbww_color
            self._color_temp = None

            self._oocsi.send(self._oocsichannel, {"colorrgbww": rgbww_color})

        if ATTR_BRIGHTNESS in kwargs and brightness_supported(supported_color_modes):
            self._brightness = kwargs.get(ATTR_BRIGHTNESS)
            self._oocsi.send(self._oocsichannel, {"brightness": self._brightness})
        if ATTR_WHITE in kwargs and COLOR_MODE_WHITE in supported_color_modes:
            self._color_mode = COLOR_MODE_WHITE
            self._brightness = kwargs.get(ATTR_WHITE)
            self._white_switch = kwargs.get(ATTR_WHITE)
            self._oocsi.send(self._oocsichannel, {"brightnessWhite": self._brightness})

        if ATTR_COLOR_TEMP in kwargs and COLOR_MODE_COLOR_TEMP in supported_color_modes:

            self._color_mode = COLOR_MODE_COLOR_TEMP
            self._color_temp = kwargs.get(ATTR_COLOR_TEMP)

            if self._ledType in ["RGB", "RGBW"]:
                CTinRGB = color_util.color_temperature_to_rgb(self._color_temp)
                self._oocsi.send(self._oocsichannel, {"colorTempInRGB": CTinRGB})
            elif self._ledType in ["CCT", "RGBWW"]:
                self._oocsi.send(self._oocsichannel, {"colorTemp": self._color_temp})

        if ATTR_EFFECT in kwargs:
            self._effect = kwargs[ATTR_EFFECT]
            self._oocsi.send(self._oocsichannel, {"effect": self._effect})

        # def colormodeRGBpicker(self):
        #     if COLOR_MODE_RGB in supported_color_modes:
        #         self._color_mode = COLOR_MODE_RGB
        #     if COLOR_MODE_RGBW in supported_color_modes:
        #         self._color_mode = COLOR_MODE_RGBW
        #     if COLOR_MODE_RGBWW in supported_color_modes:
        #         self._color_mode = COLOR_MODE_RGBWW

        # if "CCT" and "RGB" in self._spectrum:
        #     if self._color_temp != None:
        #         self._color_mode = COLOR_MODE_COLOR_TEMP
        #     else:

        #         colormodeRGBpicker

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._oocsi.send(self._oocsichannel, {"state": False})
        self._channelState = False
