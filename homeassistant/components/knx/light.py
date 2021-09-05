"""Support for KNX/IP lights."""
from __future__ import annotations

from typing import Any, Tuple, cast

from xknx import XKNX
from xknx.devices.light import Light as XknxLight, XYYColor
from xknx.telegram.address import parse_device_group_address

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_XY_COLOR,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_HS,
    COLOR_MODE_ONOFF,
    COLOR_MODE_RGB,
    COLOR_MODE_RGBW,
    COLOR_MODE_XY,
    LightEntity,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.color as color_util

from .const import DOMAIN, KNX_ADDRESS, ColorTempModes
from .knx_entity import KnxEntity
from .schema import LightSchema


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up lights for KNX platform."""
    if not discovery_info or not discovery_info["platform_config"]:
        return
    platform_config = discovery_info["platform_config"]
    xknx: XKNX = hass.data[DOMAIN].xknx

    _async_migrate_unique_id(hass, platform_config)
    async_add_entities(
        KNXLight(xknx, entity_config) for entity_config in platform_config
    )


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


def _create_light(xknx: XKNX, config: ConfigType) -> XknxLight:
    """Return a KNX Light device to be used within XKNX."""

    def individual_color_addresses(color: str, feature: str) -> Any | None:
        """Load individual color address list from configuration structure."""
        if (
            LightSchema.CONF_INDIVIDUAL_COLORS not in config
            or color not in config[LightSchema.CONF_INDIVIDUAL_COLORS]
        ):
            return None
        return config[LightSchema.CONF_INDIVIDUAL_COLORS][color].get(feature)

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
        group_address_tunable_white = config.get(LightSchema.CONF_COLOR_TEMP_ADDRESS)
        group_address_tunable_white_state = config.get(
            LightSchema.CONF_COLOR_TEMP_STATE_ADDRESS
        )

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
        group_address_hue=config.get(LightSchema.CONF_HUE_ADDRESS),
        group_address_hue_state=config.get(LightSchema.CONF_HUE_STATE_ADDRESS),
        group_address_saturation=config.get(LightSchema.CONF_SATURATION_ADDRESS),
        group_address_saturation_state=config.get(
            LightSchema.CONF_SATURATION_STATE_ADDRESS
        ),
        group_address_xyy_color=config.get(LightSchema.CONF_XYY_ADDRESS),
        group_address_xyy_color_state=config.get(LightSchema.CONF_XYY_STATE_ADDRESS),
        group_address_tunable_white=group_address_tunable_white,
        group_address_tunable_white_state=group_address_tunable_white_state,
        group_address_color_temperature=group_address_color_temp,
        group_address_color_temperature_state=group_address_color_temp_state,
        group_address_switch_red=individual_color_addresses(
            LightSchema.CONF_RED, KNX_ADDRESS
        ),
        group_address_switch_red_state=individual_color_addresses(
            LightSchema.CONF_RED, LightSchema.CONF_STATE_ADDRESS
        ),
        group_address_brightness_red=individual_color_addresses(
            LightSchema.CONF_RED, LightSchema.CONF_BRIGHTNESS_ADDRESS
        ),
        group_address_brightness_red_state=individual_color_addresses(
            LightSchema.CONF_RED, LightSchema.CONF_BRIGHTNESS_STATE_ADDRESS
        ),
        group_address_switch_green=individual_color_addresses(
            LightSchema.CONF_GREEN, KNX_ADDRESS
        ),
        group_address_switch_green_state=individual_color_addresses(
            LightSchema.CONF_GREEN, LightSchema.CONF_STATE_ADDRESS
        ),
        group_address_brightness_green=individual_color_addresses(
            LightSchema.CONF_GREEN, LightSchema.CONF_BRIGHTNESS_ADDRESS
        ),
        group_address_brightness_green_state=individual_color_addresses(
            LightSchema.CONF_GREEN, LightSchema.CONF_BRIGHTNESS_STATE_ADDRESS
        ),
        group_address_switch_blue=individual_color_addresses(
            LightSchema.CONF_BLUE, KNX_ADDRESS
        ),
        group_address_switch_blue_state=individual_color_addresses(
            LightSchema.CONF_BLUE, LightSchema.CONF_STATE_ADDRESS
        ),
        group_address_brightness_blue=individual_color_addresses(
            LightSchema.CONF_BLUE, LightSchema.CONF_BRIGHTNESS_ADDRESS
        ),
        group_address_brightness_blue_state=individual_color_addresses(
            LightSchema.CONF_BLUE, LightSchema.CONF_BRIGHTNESS_STATE_ADDRESS
        ),
        group_address_switch_white=individual_color_addresses(
            LightSchema.CONF_WHITE, KNX_ADDRESS
        ),
        group_address_switch_white_state=individual_color_addresses(
            LightSchema.CONF_WHITE, LightSchema.CONF_STATE_ADDRESS
        ),
        group_address_brightness_white=individual_color_addresses(
            LightSchema.CONF_WHITE, LightSchema.CONF_BRIGHTNESS_ADDRESS
        ),
        group_address_brightness_white_state=individual_color_addresses(
            LightSchema.CONF_WHITE, LightSchema.CONF_BRIGHTNESS_STATE_ADDRESS
        ),
        min_kelvin=config[LightSchema.CONF_MIN_KELVIN],
        max_kelvin=config[LightSchema.CONF_MAX_KELVIN],
    )


class KNXLight(KnxEntity, LightEntity):
    """Representation of a KNX light."""

    _device: XknxLight

    def __init__(self, xknx: XKNX, config: ConfigType) -> None:
        """Initialize of KNX light."""
        super().__init__(_create_light(xknx, config))
        self._max_kelvin: int = config[LightSchema.CONF_MAX_KELVIN]
        self._min_kelvin: int = config[LightSchema.CONF_MIN_KELVIN]

        self._attr_max_mireds = color_util.color_temperature_kelvin_to_mired(
            self._min_kelvin
        )
        self._attr_min_mireds = color_util.color_temperature_kelvin_to_mired(
            self._max_kelvin
        )
        self._attr_unique_id = self._device_unique_id()

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
    def is_on(self) -> bool:
        """Return true if light is on."""
        return bool(self._device.state)

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        if self._device.supports_brightness:
            return self._device.current_brightness
        if self._device.current_xyy_color is not None:
            _, brightness = self._device.current_xyy_color
            return brightness
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
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float]."""
        # Hue is scaled 0..360 int encoded in 1 byte in KNX (-> only 256 possible values)
        # Saturation is scaled 0..100 int
        return self._device.current_hs_color

    @property
    def xy_color(self) -> tuple[float, float] | None:
        """Return the xy color value [float, float]."""
        if self._device.current_xyy_color is not None:
            xy_color, _ = self._device.current_xyy_color
            return xy_color
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
    def color_mode(self) -> str | None:
        """Return the color mode of the light."""
        if self._device.supports_xyy_color:
            return COLOR_MODE_XY
        if self._device.supports_hs_color:
            return COLOR_MODE_HS
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
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        mireds = kwargs.get(ATTR_COLOR_TEMP)
        rgb = kwargs.get(ATTR_RGB_COLOR)
        rgbw = kwargs.get(ATTR_RGBW_COLOR)
        hs_color = kwargs.get(ATTR_HS_COLOR)
        xy_color = kwargs.get(ATTR_XY_COLOR)

        if (
            not self.is_on
            and brightness is None
            and mireds is None
            and rgb is None
            and rgbw is None
            and hs_color is None
            and xy_color is None
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
                    Tuple[int, int, int],
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

        if xy_color is not None:
            await self._device.set_xyy_color(
                XYYColor(color=xy_color, brightness=brightness)
            )
            return

        if hs_color is not None:
            # round so only one telegram will be sent if the other matches state
            hue = round(hs_color[0])
            sat = round(hs_color[1])
            await self._device.set_hs_color((hue, sat))

        if brightness is not None:
            # brightness: 1..255; 0 brightness will call async_turn_off()
            if self._device.brightness.writable:
                await self._device.set_brightness(brightness)
                return
            # brightness without color in kwargs; set via color
            if self.color_mode == COLOR_MODE_XY:
                await self._device.set_xyy_color(XYYColor(brightness=brightness))
                return
            # default to white if color not known for RGB(W)
            if self.color_mode == COLOR_MODE_RGBW:
                rgbw = self.rgbw_color
                if not rgbw or not any(rgbw):
                    await self._device.set_color((0, 0, 0), brightness)
                    return
                await set_color(rgbw[:3], rgbw[3], brightness)
                return
            if self.color_mode == COLOR_MODE_RGB:
                rgb = self.rgb_color
                if not rgb or not any(rgb):
                    await self._device.set_color((brightness, brightness, brightness))
                    return
                await set_color(rgb, None, brightness)
                return

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._device.set_off()
