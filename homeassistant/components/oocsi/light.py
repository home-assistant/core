"""Platform for sensor integration."""
from __future__ import annotations
from typing import Any
from homeassistant.components import light
import homeassistant.util.color as color_util

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    ATTR_WHITE,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_HS,
    COLOR_MODE_ONOFF,
    COLOR_MODE_WHITE,
    COLOR_MODE_COLOR_RGBWW,
    COLOR_MODE_COLOR_RGBW,
    SUPPORT_EFFECT,
    SUPPORT_TRANSITION,
    LightEntity,
    brightness_supported,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.core import callback
from .const import DOMAIN
from . import async_create_new_platform_entity

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
        self._color_type = entityProperty["color_mode"]
        self._color_mode: str | None = None
        self._color_temp: int | None = None
        self._white_value: int | None = None
        self._rgb_color = None
        self._supported_color_modes: set[str]
        self._hs: tuple[float, float] | None = None

    async def _color_setup(self) -> None:
        self._supported_color_modes = set()
        colortype = self._color_type

        if colortype in ["RGB", "RGBW", "RGBCCT", "CCT", "DIM"]:
            self._supported_color_modes.add(COLOR_MODE_BRIGHTNESS)
            self._color_mode = COLOR_MODE_BRIGHTNESS

        if colortype in ["RGB", "RGBW", "RGBCCT"]:
            self._supported_color_modes.add(COLOR_MODE_HS)
            self._color_mode = COLOR_MODE_HS

        if colortype in ["CCT", "RGBCCT"]:
            self._supported_color_modes.add(COLOR_MODE_COLOR_TEMP)
            self._color_mode = COLOR_MODE_COLOR_TEMP

        if colortype == "RGBCCT":
            self._supported_color_modes.add(COLOR_MODE_COLOR_RGBWW)
            self._color_mode = COLOR_MODE_COLOR_RGBWW

        if colortype == "RGBW":
            self._supported_color_modes.add(COLOR_MODE_COLOR_RGBW)
            self._color_mode = COLOR_MODE_COLOR_RGBW

    async def async_added_to_hass(self) -> None:
        """Create oocsi listener"""

        @callback
        def channelUpdateEvent(sender, recipient, event, **kwargs: Any):
            """Handle oocsi event"""
            self._channelState = event["state"]
            if self._channelState == True:
                if COLOR_MODE_HS in self._supported_color_modes:
                    self._hs = color_util.color_RGB_to_hs(
                        event["colorrgb"][0], event["colorrgb"][1], event["colorrgb"][2]
                    )
                if COLOR_MODE_BRIGHTNESS in self._supported_color_modes:
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
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hs color value."""
        if self._hs is None:
            return None
        hs_color = self._hs
        return (hs_color[0], hs_color[1])

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
    def is_on(self):
        """Return true if the switch is on."""
        return self._channelState

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""

        supported_color_modes = self._supported_color_modes or set()

        attributes: dict[str, Any] = {}

        if ATTR_HS_COLOR in kwargs and COLOR_MODE_HS in supported_color_modes:
            hs_color = kwargs.get(ATTR_HS_COLOR, self._color_temp)
            self._hs = hs_color
            attributes["color_hs"] = [hs_color[0], hs_color[1]]
            self._oocsi.send(self._oocsichannel, {"colorhs": attributes["color_hs"]})

            rgb_color = color_util.color_hs_to_RGB(hs_color[0], hs_color[1])
            attributes["color_rgb"] = [rgb_color[0], rgb_color[1], rgb_color[2]]
            self._oocsi.send(self._oocsichannel, {"colorrgb": attributes["color_rgb"]})

        if ATTR_WHITE in kwargs and COLOR_MODE_WHITE in supported_color_modes:
            self._white_value = kwargs.get(ATTR_WHITE, self._color_temp)

        if ATTR_TRANSITION in kwargs:
            attributes["transition"] = kwargs[ATTR_TRANSITION]

        if ATTR_BRIGHTNESS in kwargs and brightness_supported(supported_color_modes):
            self._brightness = kwargs.get(ATTR_BRIGHTNESS, self._brightness)

        if ATTR_COLOR_TEMP in kwargs and COLOR_MODE_COLOR_TEMP in supported_color_modes:
            self._color_temp = kwargs.get(ATTR_COLOR_TEMP, self._color_temp)
            self._oocsi.send(self._oocsichannel, {"colorTemp": self._color_temp})

        if ATTR_EFFECT in kwargs:
            attributes["effect"] = kwargs[ATTR_EFFECT]

        # if all(
        #     x in [COLOR_MODE_HS, COLOR_MODE_COLOR_TEMP] for x in supported_color_modes
        # ):
        #     print("both")
        #     if self._color_temp == 0:
        #         self._color_mode = COLOR_MODE_HS
        #     else:
        #         self._color_mode = COLOR_MODE_COLOR_TEMP
        # if all(x in [COLOR_MODE_HS, COLOR_MODE_WHITE] for x in supported_color_modes):
        #     if self._white_value == 0:
        #         self._color_mode = COLOR_MODE_HS
        #     else:
        #         self._color_mode = COLOR_MODE_WHITE

        self._oocsi.send(self._oocsichannel, {"brightness": self._brightness})
        self._channelState = True
        self._oocsi.send(self._oocsichannel, {"state": True})
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._oocsi.send(self._oocsichannel, {"state": False})
        self._channelState = False
