"""Support for KNX/IP lights."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Callable, cast

from xknx import XKNX
from xknx.devices import Light as XknxLight
from xknx.telegram.address import parse_device_group_address

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
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.color as color_util

from .const import DOMAIN, KNX_ADDRESS, ColorTempModes
from .knx_entity import KnxEntity
from .schema import LightSchema


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: Callable[[Iterable[Entity]], None],
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up lights for KNX platform."""
    if not discovery_info or not discovery_info["platform_config"]:
        return
    platform_config = discovery_info["platform_config"]
    _async_migrate_unique_id(hass, platform_config)

    xknx: XKNX = hass.data[DOMAIN].xknx
    entities = []
    for entity_config in platform_config:
        entities.append(KNXLight(xknx, entity_config))

    async_add_entities(entities)


@callback
def _async_migrate_unique_id(
    hass: HomeAssistant, platform_config: list[ConfigType]
) -> None:
    """Change unique_ids used in 2021.4 to exchange individual color switch address for brightness address."""
    entity_registry = er.async_get(hass)
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

    def __init__(self, xknx: XKNX, config: ConfigType) -> None:
        """Initialize of KNX light."""
        self._device: XknxLight
        super().__init__(self._create_light(xknx, config))
        self._unique_id = self._device_unique_id()
        self._min_kelvin: int = config[LightSchema.CONF_MIN_KELVIN]
        self._max_kelvin: int = config[LightSchema.CONF_MAX_KELVIN]
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

    @staticmethod
    def _create_light(xknx: XKNX, config: ConfigType) -> XknxLight:
        """Return a KNX Light device to be used within XKNX."""

        def create_light_color(
            color: str, config: ConfigType
        ) -> tuple[str | None, str | None, str | None, str | None]:
            """Load color configuration from configuration structure."""
            if "individual_colors" in config and color in config["individual_colors"]:
                sub_config = config["individual_colors"][color]
                group_address_switch = sub_config.get(KNX_ADDRESS)
                group_address_switch_state = sub_config.get(
                    LightSchema.CONF_STATE_ADDRESS
                )
                group_address_brightness = sub_config.get(
                    LightSchema.CONF_BRIGHTNESS_ADDRESS
                )
                group_address_brightness_state = sub_config.get(
                    LightSchema.CONF_BRIGHTNESS_STATE_ADDRESS
                )
                return (
                    group_address_switch,
                    group_address_switch_state,
                    group_address_brightness,
                    group_address_brightness_state,
                )
            return None, None, None, None

        group_address_tunable_white = None
        group_address_tunable_white_state = None
        group_address_color_temp = None
        group_address_color_temp_state = None
        if config[LightSchema.CONF_COLOR_TEMP_MODE] == ColorTempModes.ABSOLUTE:
            group_address_color_temp = config.get(LightSchema.CONF_COLOR_TEMP_ADDRESS)
            group_address_color_temp_state = config.get(
                LightSchema.CONF_COLOR_TEMP_STATE_ADDRESS
            )
        elif config[LightSchema.CONF_COLOR_TEMP_MODE] == ColorTempModes.RELATIVE:
            group_address_tunable_white = config.get(
                LightSchema.CONF_COLOR_TEMP_ADDRESS
            )
            group_address_tunable_white_state = config.get(
                LightSchema.CONF_COLOR_TEMP_STATE_ADDRESS
            )

        (
            red_switch,
            red_switch_state,
            red_brightness,
            red_brightness_state,
        ) = create_light_color(LightSchema.CONF_RED, config)
        (
            green_switch,
            green_switch_state,
            green_brightness,
            green_brightness_state,
        ) = create_light_color(LightSchema.CONF_GREEN, config)
        (
            blue_switch,
            blue_switch_state,
            blue_brightness,
            blue_brightness_state,
        ) = create_light_color(LightSchema.CONF_BLUE, config)
        (
            white_switch,
            white_switch_state,
            white_brightness,
            white_brightness_state,
        ) = create_light_color(LightSchema.CONF_WHITE, config)

        return XknxLight(
            xknx,
            name=config[CONF_NAME],
            group_address_switch=config.get(KNX_ADDRESS),
            group_address_switch_state=config.get(LightSchema.CONF_STATE_ADDRESS),
            group_address_brightness=config.get(LightSchema.CONF_BRIGHTNESS_ADDRESS),
            group_address_brightness_state=config.get(
                LightSchema.CONF_BRIGHTNESS_STATE_ADDRESS
            ),
            group_address_color=config.get(LightSchema.CONF_COLOR_ADDRESS),
            group_address_color_state=config.get(LightSchema.CONF_COLOR_STATE_ADDRESS),
            group_address_rgbw=config.get(LightSchema.CONF_RGBW_ADDRESS),
            group_address_rgbw_state=config.get(LightSchema.CONF_RGBW_STATE_ADDRESS),
            group_address_tunable_white=group_address_tunable_white,
            group_address_tunable_white_state=group_address_tunable_white_state,
            group_address_color_temperature=group_address_color_temp,
            group_address_color_temperature_state=group_address_color_temp_state,
            group_address_switch_red=red_switch,
            group_address_switch_red_state=red_switch_state,
            group_address_brightness_red=red_brightness,
            group_address_brightness_red_state=red_brightness_state,
            group_address_switch_green=green_switch,
            group_address_switch_green_state=green_switch_state,
            group_address_brightness_green=green_brightness,
            group_address_brightness_green_state=green_brightness_state,
            group_address_switch_blue=blue_switch,
            group_address_switch_blue_state=blue_switch_state,
            group_address_brightness_blue=blue_brightness,
            group_address_brightness_blue_state=blue_brightness_state,
            group_address_switch_white=white_switch,
            group_address_switch_white_state=white_switch_state,
            group_address_brightness_white=white_brightness,
            group_address_brightness_white_state=white_brightness_state,
            min_kelvin=config[LightSchema.CONF_MIN_KELVIN],
            max_kelvin=config[LightSchema.CONF_MAX_KELVIN],
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
