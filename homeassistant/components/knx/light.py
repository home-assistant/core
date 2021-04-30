"""Support for KNX/IP lights."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Callable, cast

from xknx.devices import Light as XknxLight

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_ONOFF,
    COLOR_MODE_RGB,
    COLOR_MODE_RGBW,
    LightEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.color as color_util

from .const import DOMAIN
from .knx_entity import KnxEntity
from .schema import LightSchema


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: Callable[[Iterable[Entity]], None],
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up lights for KNX platform."""
    entities = []
    for device in hass.data[DOMAIN].xknx.devices:
        if isinstance(device, XknxLight):
            entities.append(KNXLight(device))
    async_add_entities(entities)


class KNXLight(KnxEntity, LightEntity):
    """Representation of a KNX light."""

    def __init__(self, device: XknxLight) -> None:
        """Initialize of KNX light."""
        self._device: XknxLight
        super().__init__(device)
        self._unique_id = self._device_unique_id()
        self._min_kelvin = device.min_kelvin or LightSchema.DEFAULT_MIN_KELVIN
        self._max_kelvin = device.max_kelvin or LightSchema.DEFAULT_MAX_KELVIN
        self._min_mireds = color_util.color_temperature_kelvin_to_mired(
            self._max_kelvin
        )
        self._max_mireds = color_util.color_temperature_kelvin_to_mired(
            self._min_kelvin
        )

    def _device_unique_id(self) -> str:
        """Return unique id for this device."""
        if self._device.switch.group_address is not None:
            return f"{self._device.switch.group_address}"
        return (
            f"{self._device.red.switch.group_address}_"
            f"{self._device.green.switch.group_address}_"
            f"{self._device.blue.switch.group_address}_"
            f"{self._device.white.switch.group_address}"
        )

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return bool(self._device.state)

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        if self._device.supports_brightness:
            return self._device.current_brightness
        if (rgb := self.rgb_color) is not None:
            return max(rgb)
        return None

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the rgb color value [int, int, int]."""
        if (rgbw := self.rgbw_color) is not None:
            # used in brightness calculation when no address is given
            return color_util.color_rgbw_to_rgb(*rgbw)
        if self._device.supports_color:
            rgb, _ = self._device.current_color
            return rgb
        return None

    @property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Return the rgbw color value [int, int, int, int]."""
        if self._device.supports_rgbw:
            rgb, white = self._device.current_color
            if rgb is not None and white is not None:
                return (*rgb, white)
        return None

    @property
    def color_temp(self) -> int | None:
        """Return the color temperature in mireds."""
        if self._device.supports_color_temperature:
            kelvin = self._device.current_color_temperature
            # Avoid division by zero if actuator reported 0 Kelvin (e.g., uninitialized DALI-Gateway)
            if kelvin is not None and kelvin > 0:
                return color_util.color_temperature_kelvin_to_mired(kelvin)
        if self._device.supports_tunable_white:
            relative_ct = self._device.current_tunable_white
            if relative_ct is not None:
                # as KNX devices typically use Kelvin we use it as base for
                # calculating ct from percent
                return color_util.color_temperature_kelvin_to_mired(
                    self._min_kelvin
                    + ((relative_ct / 255) * (self._max_kelvin - self._min_kelvin))
                )
        return None

    @property
    def min_mireds(self) -> int:
        """Return the coldest color temp this light supports in mireds."""
        return self._min_mireds

    @property
    def max_mireds(self) -> int:
        """Return the warmest color temp this light supports in mireds."""
        return self._max_mireds

    @property
    def color_mode(self) -> str | None:
        """Return the color mode of the light."""
        if self._device.supports_rgbw:
            return COLOR_MODE_RGBW
        if self._device.supports_color:
            return COLOR_MODE_RGB
        if (
            self._device.supports_color_temperature
            or self._device.supports_tunable_white
        ):
            return COLOR_MODE_COLOR_TEMP
        if self._device.supports_brightness:
            return COLOR_MODE_BRIGHTNESS
        return COLOR_MODE_ONOFF

    @property
    def supported_color_modes(self) -> set | None:
        """Flag supported color modes."""
        return {self.color_mode}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        # ignore arguments if not supported to fall back to set_on()
        brightness = (
            kwargs.get(ATTR_BRIGHTNESS)
            if self._device.supports_brightness
            or self.color_mode in (COLOR_MODE_RGB, COLOR_MODE_RGBW)
            else None
        )
        mireds = (
            kwargs.get(ATTR_COLOR_TEMP)
            if self.color_mode == COLOR_MODE_COLOR_TEMP
            else None
        )
        rgb = kwargs.get(ATTR_RGB_COLOR) if self.color_mode == COLOR_MODE_RGB else None
        rgbw = (
            kwargs.get(ATTR_RGBW_COLOR) if self.color_mode == COLOR_MODE_RGBW else None
        )

        if (
            not self.is_on
            and brightness is None
            and mireds is None
            and rgb is None
            and rgbw is None
        ):
            await self._device.set_on()
            return

        async def set_color(
            rgb: tuple[int, int, int], white: int | None, brightness: int | None
        ) -> None:
            """Set color of light. Normalize colors for brightness when not writable."""
            if brightness:
                if self._device.brightness.writable:
                    await self._device.set_color(rgb, white)
                    await self._device.set_brightness(brightness)
                    return
                rgb = cast(
                    tuple[int, int, int],
                    tuple(color * brightness // 255 for color in rgb),
                )
                white = white * brightness // 255 if white is not None else None
            await self._device.set_color(rgb, white)

        # return after RGB(W) color has changed as it implicitly sets the brightness
        if rgbw is not None:
            await set_color(rgbw[:3], rgbw[3], brightness)
            return
        if rgb is not None:
            await set_color(rgb, None, brightness)
            return

        if mireds is not None:
            kelvin = int(color_util.color_temperature_mired_to_kelvin(mireds))
            kelvin = min(self._max_kelvin, max(self._min_kelvin, kelvin))

            if self._device.supports_color_temperature:
                await self._device.set_color_temperature(kelvin)
            elif self._device.supports_tunable_white:
                relative_ct = int(
                    255
                    * (kelvin - self._min_kelvin)
                    / (self._max_kelvin - self._min_kelvin)
                )
                await self._device.set_tunable_white(relative_ct)

        if brightness is not None:
            await self._device.set_brightness(brightness)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._device.set_off()
