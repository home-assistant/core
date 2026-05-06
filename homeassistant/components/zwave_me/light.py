"""Representation of an RGB light."""

from __future__ import annotations

from typing import Any

from zwave_me_ws import ZWaveMeData

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ZWaveMePlatform
from .controller import ZWaveMeConfigEntry, ZWaveMeController
from .entity import ZWaveMeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ZWaveMeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the rgb platform."""

    @callback
    def add_new_device(new_device: ZWaveMeData) -> None:
        """Add a new device."""
        async_add_entities([ZWaveMeRGB(config_entry.runtime_data, new_device)])

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
            self._attr_supported_features = LightEntityFeature.TRANSITION
        self._attr_supported_color_modes: set[ColorMode] = {self._attr_color_mode}

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device on."""
        self.controller.zwave_api.send_command(self.device.id, "off")

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        color: tuple[int, int, int] | None = kwargs.get(ATTR_RGB_COLOR)
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        transition: float | None = kwargs.get(ATTR_TRANSITION)

        command_id = "exact"
        command_args: dict[str, str] = {}

        # set color levels
        if color is not None:
            if not any(color):
                color = (255, 255, 255)
            command_args.update(
                {"red": str(color[0]), "green": str(color[1]), "blue": str(color[2])}
            )
        elif brightness is not None:
            command_args["level"] = str(round(brightness / 2.55))
        elif transition is not None:
            command_args["level"] = "100"
        else:
            command_id = "on"

        if transition is not None:
            command_id = "exactSmooth"
            if transition < 127:
                duration = round(transition)
            else:
                duration = min(127, round((transition) / 60)) + 127
            command_args["duration"] = str(duration)

        cmd = command_id
        if command_args:
            cmd = f"{command_id}?{'&'.join(f'{argId}={argVal}' for argId, argVal in command_args.items())}"
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
