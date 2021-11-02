"""Platform for sensor integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_WHITE,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_ONOFF,
    COLOR_MODE_RGB,
    COLOR_MODE_RGBW,
    COLOR_MODE_RGBWW,
    COLOR_MODE_WHITE,
    SUPPORT_EFFECT,
    LightEntity,
    brightness_supported,
)
from homeassistant.core import callback
import homeassistant.util.color as color_util

from . import async_create_new_platform_entity
from .const import DOMAIN


# Handle platform
async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Oocsi light platform."""

    # Add the corresponding oocsi server
    api = hass.data[DOMAIN][config_entry.entry_id]
    platform = "light"

    # Create entities >  __init__.py
    await async_create_new_platform_entity(
        hass, config_entry, api, BasicLight, async_add_entities, platform
    )


class BasicLight(LightEntity):
    """variable oocsi lamp object."""

    # Import & configure entity
    def __init__(self, hass, entity_name, api, entityProperty, device):
        """Set up all relevant variables."""
        # Basic variables
        self._supported_color_modes: set[str] | None = None
        self._hass = hass
        self._oocsi = api
        self._name = entity_name

        self._attr_device_info = {
            "name": entity_name,
            "manufacturer": entityProperty["creator"],
            "via_device_id": device,
        }

        # Set properties
        self._entity_property = entityProperty
        self._attr_unique_id = entityProperty["channel_name"]
        self._oocsichannel = entityProperty["channel_name"]
        self._channel_state = entityProperty["state"]

        if "logo" in entityProperty:
            self._icon = entityProperty["logo"]
        else:
            self._icon = "mdi:light"
        # self._supportedFeature = entityProperty["type"]

        self._brightness = entityProperty["brightness"]
        self._led_type = entityProperty["led_type"]
        self._spectrum = entityProperty["spectrum"]

        self._color_temp: int | None = None
        self._color_mode: str | None = None
        self._supported_features = 0
        self._supported_color_modes: set[str]
        self._rgb: tuple[int, int, int] | None = None
        self._rgbw: tuple[int, int, int, int] | None = None
        self._rgbww: tuple[int, int, int, int, int] | None = None

        if entityProperty.get("effect"):
            self._attr_supported_features |= SUPPORT_EFFECT
            self._effect: str | None = None
            self._effect_list = entityProperty["effect"]

    async def _color_setup(self):
        """Pick the right config for the specified lamp."""
        self._supported_color_modes = set()
        led_type = self._led_type

        if led_type in ["RGB", "RGBW", "RGBWW"]:

            spectrum = self._spectrum

            if "WHITE" in spectrum:
                self._supported_color_modes.add(COLOR_MODE_WHITE)

            if "CCT" in spectrum:
                self._supported_color_modes.add(COLOR_MODE_COLOR_TEMP)

            if "RGB" in spectrum:
                if led_type == "RGBWW":
                    self._supported_color_modes.add(COLOR_MODE_RGBWW)
                    self._color_mode = COLOR_MODE_RGBWW

                if led_type == "RGBW":
                    self._supported_color_modes.add(COLOR_MODE_RGBW)
                    self._color_mode = COLOR_MODE_RGBW

                if led_type == "RGB":
                    self._supported_color_modes.add(COLOR_MODE_RGB)
                    self._color_mode = COLOR_MODE_RGB

        if led_type == "WHITE":
            self._supported_color_modes.add(COLOR_MODE_WHITE)

        if led_type == "CCT":
            self._attr_max_mireds = self._entity_property["max_mireds"]
            self._attr_min_mireds = self._entity_property["min_mireds"]
            self._supported_color_modes.add(COLOR_MODE_COLOR_TEMP)

        if led_type == "DIMMABLE":
            self._supported_color_modes.add(COLOR_MODE_BRIGHTNESS)

        if led_type == "ONOFF":
            self._supported_color_modes.add(COLOR_MODE_ONOFF)

    async def async_added_to_hass(self) -> None:
        """Create oocsi listener."""

        @callback
        def channel_update_event(sender, recipient, event, **kwargs: Any):
            """Handle oocsi event."""
            supported_color_modes = self._supported_color_modes or set()
            self._channel_state = event["state"]
            if COLOR_MODE_RGB in supported_color_modes:
                self._rgb = event["colorrgb"]
            if COLOR_MODE_RGBW in supported_color_modes:
                self._rgbw = event["colorrgbw"]
            if COLOR_MODE_RGBWW in supported_color_modes:
                self._rgbww = event["colorrgbww"]
            if brightness_supported(supported_color_modes):
                self._brightness = event["brightness"]
            if COLOR_MODE_COLOR_TEMP in supported_color_modes:
                self._color_temp = event["color_temp"]
            if COLOR_MODE_WHITE in supported_color_modes:
                self._brightness = event["white"]

            self.async_write_ha_state()

        await self._color_setup()
        self._oocsi.subscribe(self._oocsichannel, channel_update_event)

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
        """Return the rgb color value."""

        if self._rgb is None:
            return None
        rgb_color = self._rgb
        return (rgb_color[0], rgb_color[1], rgb_color[2])

    @property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Return the rgb color value."""

        if self._rgbw is None:
            return None
        rgbw_color = self._rgbw
        return (rgbw_color[0], rgbw_color[1], rgbw_color[2], rgbw_color[3])

    @property
    def rgbww_color(self) -> tuple[int, int, int, int, int] | None:
        """Return the rgb color value."""

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
        """Show important device info."""
        return {"name": self._name}

    @property
    def icon(self) -> str:
        """Return the icon."""
        # return self._static_info.icon
        return self._icon

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        return self._effect

    @property
    def effect_list(self) -> list[str] | None:
        """Return the list of supported effects."""
        return self._effect_list

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._supported_features

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return self._channel_state

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self._channel_state = True
        self._oocsi.send(self._oocsichannel, {"state": True})
        supported_color_modes = self._supported_color_modes or set()

        if ATTR_RGB_COLOR in kwargs and COLOR_MODE_RGB in supported_color_modes:
            self._color_mode = COLOR_MODE_RGB
            self._rgb = kwargs.get(ATTR_RGB_COLOR)
            self._oocsi.send(self._oocsichannel, {"colorrgb": self._rgb})

        if ATTR_RGBW_COLOR in kwargs and COLOR_MODE_RGBW in supported_color_modes:
            self._color_mode = COLOR_MODE_RGBW
            self._rgbw = kwargs.get(ATTR_RGBW_COLOR)
            self._oocsi.send(self._oocsichannel, {"colorrgbw": self._rgbw})

        if ATTR_RGBWW_COLOR in kwargs and COLOR_MODE_RGBWW in supported_color_modes:
            self._color_mode = COLOR_MODE_RGBWW
            self._rgbww = kwargs.get(ATTR_RGBWW_COLOR)
            self._oocsi.send(self._oocsichannel, {"colorrgbww": self._rgbww})

        if ATTR_BRIGHTNESS in kwargs and brightness_supported(supported_color_modes):
            self._brightness = kwargs.get(ATTR_BRIGHTNESS)
            self._oocsi.send(self._oocsichannel, {"brightness": self._brightness})

        if ATTR_WHITE in kwargs and COLOR_MODE_WHITE in supported_color_modes:
            self._color_mode = COLOR_MODE_WHITE
            self._brightness = kwargs.get(ATTR_WHITE)
            self._oocsi.send(self._oocsichannel, {"brightnessWhite": self._brightness})

        if ATTR_COLOR_TEMP in kwargs and COLOR_MODE_COLOR_TEMP in supported_color_modes:
            self._color_mode = COLOR_MODE_COLOR_TEMP
            self._color_temp = kwargs[ATTR_COLOR_TEMP]

            if self._led_type in ["RGB", "RGBW"]:
                ct_in_rgb = color_util.color_temperature_to_rgb(
                    *kwargs[ATTR_COLOR_TEMP]
                )
                self._oocsi.send(self._oocsichannel, {"colorTempInRGB": ct_in_rgb})
            elif self._led_type in ["CCT", "RGBWW"]:
                self._oocsi.send(self._oocsichannel, {"colorTemp": self._color_temp})

        if ATTR_EFFECT in kwargs:
            self._effect = kwargs[ATTR_EFFECT]
            self._oocsi.send(self._oocsichannel, {"effect": self._effect})

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._oocsi.send(self._oocsichannel, {"state": False})
        self._channel_state = False
