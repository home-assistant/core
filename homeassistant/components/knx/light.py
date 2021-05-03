"""Support for KNX/IP lights."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Callable

from xknx.devices import Light as XknxLight
from xknx.telegram.address import parse_device_group_address

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_WHITE_VALUE,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_WHITE_VALUE,
    LightEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.color as color_util

from .const import DOMAIN, KNX_ADDRESS
from .knx_entity import KnxEntity
from .schema import LightSchema

DEFAULT_COLOR = (0.0, 0.0)
DEFAULT_BRIGHTNESS = 255
DEFAULT_WHITE_VALUE = 255


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: Callable[[Iterable[Entity]], None],
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up lights for KNX platform."""
    _async_migrate_unique_id(hass, discovery_info)
    entities = []
    for device in hass.data[DOMAIN].xknx.devices:
        if isinstance(device, XknxLight):
            entities.append(KNXLight(device))
    async_add_entities(entities)


@callback
def _async_migrate_unique_id(
    hass: HomeAssistant, discovery_info: DiscoveryInfoType | None
) -> None:
    """Change unique_ids used in 2021.4 to exchange individual color switch address for brightness address."""
    entity_registry = er.async_get(hass)
    if not discovery_info or not discovery_info["platform_config"]:
        return

    platform_config = discovery_info["platform_config"]
    for entity_config in platform_config:
        individual_colors_config = entity_config.get(LightSchema.CONF_INDIVIDUAL_COLORS)
        if individual_colors_config is None:
            continue
        try:
            ga_red_switch = individual_colors_config[LightSchema.CONF_RED][KNX_ADDRESS][
                0
            ]
            ga_green_switch = individual_colors_config[LightSchema.CONF_GREEN][
                KNX_ADDRESS
            ][0]
            ga_blue_switch = individual_colors_config[LightSchema.CONF_BLUE][
                KNX_ADDRESS
            ][0]
        except KeyError:
            continue
        # normalize group address strings
        ga_red_switch = parse_device_group_address(ga_red_switch)
        ga_green_switch = parse_device_group_address(ga_green_switch)
        ga_blue_switch = parse_device_group_address(ga_blue_switch)
        # white config is optional so it has to be checked for `None` extra
        white_config = individual_colors_config.get(LightSchema.CONF_WHITE)
        white_switch = (
            white_config.get(KNX_ADDRESS) if white_config is not None else None
        )
        ga_white_switch = (
            parse_device_group_address(white_switch[0])
            if white_switch is not None
            else None
        )

        old_uid = (
            f"{ga_red_switch}_"
            f"{ga_green_switch}_"
            f"{ga_blue_switch}_"
            f"{ga_white_switch}"
        )
        entity_id = entity_registry.async_get_entity_id("light", DOMAIN, old_uid)
        if entity_id is None:
            continue

        ga_red_brightness = parse_device_group_address(
            individual_colors_config[LightSchema.CONF_RED][
                LightSchema.CONF_BRIGHTNESS_ADDRESS
            ][0]
        )
        ga_green_brightness = parse_device_group_address(
            individual_colors_config[LightSchema.CONF_GREEN][
                LightSchema.CONF_BRIGHTNESS_ADDRESS
            ][0]
        )
        ga_blue_brightness = parse_device_group_address(
            individual_colors_config[LightSchema.CONF_BLUE][
                LightSchema.CONF_BRIGHTNESS_ADDRESS
            ][0]
        )

        new_uid = f"{ga_red_brightness}_{ga_green_brightness}_{ga_blue_brightness}"
        entity_registry.async_update_entity(entity_id, new_unique_id=new_uid)


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
            f"{self._device.red.brightness.group_address}_"
            f"{self._device.green.brightness.group_address}_"
            f"{self._device.blue.brightness.group_address}"
        )

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        if self._device.supports_brightness:
            return self._device.current_brightness
        hsv_color = self._hsv_color
        if self._device.supports_color and hsv_color:
            return round(hsv_color[-1] / 100 * 255)
        return None

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the HS color value."""
        rgb: tuple[int, int, int] | None = None
        if self._device.supports_rgbw or self._device.supports_color:
            rgb, _ = self._device.current_color
        return color_util.color_RGB_to_hs(*rgb) if rgb else None

    @property
    def _hsv_color(self) -> tuple[float, float, float] | None:
        """Return the HSV color value."""
        rgb: tuple[int, int, int] | None = None
        if self._device.supports_rgbw or self._device.supports_color:
            rgb, _ = self._device.current_color
        return color_util.color_RGB_to_hsv(*rgb) if rgb else None

    @property
    def white_value(self) -> int | None:
        """Return the white value."""
        white: int | None = None
        if self._device.supports_rgbw:
            _, white = self._device.current_color
        return white

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
    def effect_list(self) -> list[str] | None:
        """Return the list of supported effects."""
        return None

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        return None

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return bool(self._device.state)

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        flags = 0
        if self._device.supports_brightness:
            flags |= SUPPORT_BRIGHTNESS
        if self._device.supports_color:
            flags |= SUPPORT_COLOR | SUPPORT_BRIGHTNESS
        if self._device.supports_rgbw:
            flags |= SUPPORT_COLOR | SUPPORT_WHITE_VALUE
        if (
            self._device.supports_color_temperature
            or self._device.supports_tunable_white
        ):
            flags |= SUPPORT_COLOR_TEMP
        return flags

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, self.brightness)
        hs_color = kwargs.get(ATTR_HS_COLOR, self.hs_color)
        white_value = kwargs.get(ATTR_WHITE_VALUE, self.white_value)
        mireds = kwargs.get(ATTR_COLOR_TEMP, self.color_temp)

        update_brightness = ATTR_BRIGHTNESS in kwargs
        update_color = ATTR_HS_COLOR in kwargs
        update_white_value = ATTR_WHITE_VALUE in kwargs
        update_color_temp = ATTR_COLOR_TEMP in kwargs

        # avoid conflicting changes and weird effects
        if not (
            self.is_on
            or update_brightness
            or update_color
            or update_white_value
            or update_color_temp
        ):
            await self._device.set_on()

        if self._device.supports_brightness and (
            update_brightness and not update_color
        ):
            # if we don't need to update the color, try updating brightness
            # directly if supported; don't do it if color also has to be
            # changed, as RGB color implicitly sets the brightness as well
            await self._device.set_brightness(brightness)
        elif (self._device.supports_rgbw or self._device.supports_color) and (
            update_brightness or update_color or update_white_value
        ):
            # change RGB color, white value (if supported), and brightness
            # if brightness or hs_color was not yet set use the default value
            # to calculate RGB from as a fallback
            if brightness is None:
                brightness = DEFAULT_BRIGHTNESS
            if hs_color is None:
                hs_color = DEFAULT_COLOR
            if white_value is None and self._device.supports_rgbw:
                white_value = DEFAULT_WHITE_VALUE
            hsv_color = hs_color + (brightness * 100 / 255,)
            rgb = color_util.color_hsv_to_RGB(*hsv_color)
            await self._device.set_color(rgb, white_value)

        if update_color_temp:
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

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._device.set_off()
