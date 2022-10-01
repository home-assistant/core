"""Representation of an RGB light."""
from __future__ import annotations

from typing import Any

from zwave_me_ws import ZWaveMeData

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ZWaveMeController, ZWaveMeEntity
from .const import DOMAIN, ZWaveMePlatform


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the rgb platform."""

    @callback
    def add_new_device(new_device: ZWaveMeData) -> None:
        """Add a new device."""
        controller = hass.data[DOMAIN][config_entry.entry_id]
        rgb = ZWaveMeRGB(controller, new_device)

        async_add_entities(
            [
                rgb,
            ]
        )

    async_dispatcher_connect(
        hass, f"ZWAVE_ME_NEW_{ZWaveMePlatform.RGB_LIGHT.upper()}", add_new_device
    )
    async_dispatcher_connect(
        hass, f"ZWAVE_ME_NEW_{ZWaveMePlatform.RGBW_LIGHT.upper()}", add_new_device
    )
    async_dispatcher_connect(
        hass, f"ZWAVE_ME_NEW_{ZWaveMePlatform.BRIGHTNESS_LIGHT.upper()}", add_new_device
    )


class ZWaveMeRGB(ZWaveMeEntity, LightEntity):
    """Representation of a ZWaveMe light."""

    def __init__(
        self,
        controller: ZWaveMeController,
        device: ZWaveMeData,
    ) -> None:
        """Initialize the device."""
        super().__init__(controller=controller, device=device)
        if device.deviceType in [ZWaveMePlatform.RGB_LIGHT, ZWaveMePlatform.RGBW_LIGHT]:
            self._attr_color_mode = ColorMode.RGB
        else:
            self._attr_color_mode = ColorMode.BRIGHTNESS
        self._attr_supported_color_modes: set[ColorMode] = {self._attr_color_mode}

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device on."""
        self.controller.zwave_api.send_command(self.device.id, "off")

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        color = kwargs.get(ATTR_RGB_COLOR)

        if color is None:
            brightness = kwargs.get(ATTR_BRIGHTNESS)
            if brightness is None:
                self.controller.zwave_api.send_command(self.device.id, "on")
            else:
                self.controller.zwave_api.send_command(
                    self.device.id, f"exact?level={round(brightness / 2.55)}"
                )
            return
        cmd = "exact?red={}&green={}&blue={}".format(
            *color if any(color) else 255, 255, 255
        )
        self.controller.zwave_api.send_command(self.device.id, cmd)

    @property
    def is_on(self) -> bool:
        """Return true if the light is on."""
        return self.device.level == "on"

    @property
    def brightness(self) -> int:
        """Return the brightness of a device."""
        return max(self.device.color.values())

    @property
    def rgb_color(self) -> tuple[int, int, int]:
        """Return the rgb color value [int, int, int]."""
        rgb = self.device.color
        return rgb["r"], rgb["g"], rgb["b"]
