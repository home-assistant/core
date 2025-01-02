"""Support for LimitlessLED bulbs."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any, Concatenate, cast

from limitlessled import Color
from limitlessled.bridge import Bridge
from limitlessled.group import Group
from limitlessled.group.dimmer import DimmerGroup
from limitlessled.group.rgbw import RgbwGroup
from limitlessled.group.rgbww import RgbwwGroup
from limitlessled.group.white import WhiteGroup
from limitlessled.pipeline import Pipeline
from limitlessled.presets import COLORLOOP
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_FLASH,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    EFFECT_COLORLOOP,
    EFFECT_WHITE,
    FLASH_LONG,
    PLATFORM_SCHEMA as LIGHT_PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TYPE, STATE_ON
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.color import color_hs_to_RGB

_LOGGER = logging.getLogger(__name__)

CONF_BRIDGES = "bridges"
CONF_GROUPS = "groups"
CONF_NUMBER = "number"
CONF_VERSION = "version"
CONF_FADE = "fade"

DEFAULT_LED_TYPE = "rgbw"
DEFAULT_PORT = 5987
DEFAULT_TRANSITION = 0
DEFAULT_VERSION = 6
DEFAULT_FADE = False

LED_TYPE = ["rgbw", "rgbww", "white", "bridge-led", "dimmer"]

EFFECT_NIGHT = "night"

MIN_SATURATION = 10

WHITE = (0, 0)

COLOR_MODES_LIMITLESS_WHITE = {ColorMode.COLOR_TEMP}
SUPPORT_LIMITLESSLED_WHITE = LightEntityFeature.EFFECT | LightEntityFeature.TRANSITION
COLOR_MODES_LIMITLESS_DIMMER = {ColorMode.BRIGHTNESS}
SUPPORT_LIMITLESSLED_DIMMER = LightEntityFeature.TRANSITION
COLOR_MODES_LIMITLESS_RGB = {ColorMode.HS}
SUPPORT_LIMITLESSLED_RGB = (
    LightEntityFeature.EFFECT | LightEntityFeature.FLASH | LightEntityFeature.TRANSITION
)
COLOR_MODES_LIMITLESS_RGBWW = {ColorMode.COLOR_TEMP, ColorMode.HS}
SUPPORT_LIMITLESSLED_RGBWW = (
    LightEntityFeature.EFFECT | LightEntityFeature.FLASH | LightEntityFeature.TRANSITION
)

PLATFORM_SCHEMA = LIGHT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_BRIDGES): vol.All(
            cv.ensure_list,
            [
                {
                    vol.Required(CONF_HOST): cv.string,
                    vol.Optional(
                        CONF_VERSION, default=DEFAULT_VERSION
                    ): cv.positive_int,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                    vol.Required(CONF_GROUPS): vol.All(
                        cv.ensure_list,
                        [
                            {
                                vol.Required(CONF_NAME): cv.string,
                                vol.Optional(
                                    CONF_TYPE, default=DEFAULT_LED_TYPE
                                ): vol.In(LED_TYPE),
                                vol.Required(CONF_NUMBER): cv.positive_int,
                                vol.Optional(
                                    CONF_FADE, default=DEFAULT_FADE
                                ): cv.boolean,
                            }
                        ],
                    ),
                }
            ],
        )
    }
)


def rewrite_legacy(config: ConfigType) -> ConfigType:
    """Rewrite legacy configuration to new format."""
    bridges = config.get(CONF_BRIDGES, [config])
    new_bridges = []
    for bridge_conf in bridges:
        groups = []
        if "groups" in bridge_conf:
            groups = bridge_conf["groups"]
        else:
            _LOGGER.warning("Legacy configuration format detected")
            for i in range(1, 5):
                name_key = f"group_{i}_name"
                if name_key in bridge_conf:
                    groups.append(
                        {
                            "number": i,
                            "type": bridge_conf.get(
                                f"group_{i}_type", DEFAULT_LED_TYPE
                            ),
                            "name": bridge_conf.get(name_key),
                        }
                    )
        new_bridges.append(
            {
                "host": bridge_conf.get(CONF_HOST),
                "version": bridge_conf.get(CONF_VERSION),
                "port": bridge_conf.get(CONF_PORT),
                "groups": groups,
            }
        )
    return {"bridges": new_bridges}


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the LimitlessLED lights."""

    # Two legacy configuration formats are supported to maintain backwards
    # compatibility.
    config = rewrite_legacy(config)

    # Use the expanded configuration format.
    lights = []
    bridge_conf: dict[str, Any]
    group_conf: dict[str, Any]
    for bridge_conf in config[CONF_BRIDGES]:
        bridge = Bridge(
            bridge_conf.get(CONF_HOST),
            port=bridge_conf.get(CONF_PORT, DEFAULT_PORT),
            version=bridge_conf.get(CONF_VERSION, DEFAULT_VERSION),
        )
        for group_conf in bridge_conf[CONF_GROUPS]:
            group = bridge.add_group(
                group_conf.get(CONF_NUMBER),
                group_conf.get(CONF_NAME),
                group_conf.get(CONF_TYPE, DEFAULT_LED_TYPE),
            )
            lights.append(LimitlessLEDGroup(group, {"fade": group_conf[CONF_FADE]}))
    add_entities(lights)


def state[_LimitlessLEDGroupT: LimitlessLEDGroup, **_P](
    new_state: bool,
) -> Callable[
    [Callable[Concatenate[_LimitlessLEDGroupT, int, Pipeline, _P], Any]],
    Callable[Concatenate[_LimitlessLEDGroupT, _P], None],
]:
    """State decorator.

    Specify True (turn on) or False (turn off).
    """

    def decorator(
        function: Callable[Concatenate[_LimitlessLEDGroupT, int, Pipeline, _P], Any],
    ) -> Callable[Concatenate[_LimitlessLEDGroupT, _P], None]:
        """Set up the decorator function."""

        def wrapper(
            self: _LimitlessLEDGroupT, *args: _P.args, **kwargs: _P.kwargs
        ) -> None:
            """Wrap a group state change."""
            pipeline = Pipeline()
            transition_time = DEFAULT_TRANSITION
            if self.effect == EFFECT_COLORLOOP:
                self.group.stop()
            self._attr_effect = None
            # Set transition time.
            if ATTR_TRANSITION in kwargs:
                transition_time = int(cast(float, kwargs[ATTR_TRANSITION]))
            # Do group type-specific work.
            function(self, transition_time, pipeline, *args, **kwargs)
            # Update state.
            self._attr_is_on = new_state
            self.group.enqueue(pipeline)
            self.schedule_update_ha_state()

        return wrapper

    return decorator


class LimitlessLEDGroup(LightEntity, RestoreEntity):
    """Representation of a LimitessLED group."""

    _attr_assumed_state = True
    _attr_min_color_temp_kelvin = 2700  # 370 Mireds
    _attr_max_color_temp_kelvin = 6500  # 154 Mireds
    _attr_should_poll = False

    def __init__(self, group: Group, config: dict[str, Any]) -> None:
        """Initialize a group."""

        if isinstance(group, WhiteGroup):
            self._attr_supported_color_modes = COLOR_MODES_LIMITLESS_WHITE
            self._attr_supported_features = SUPPORT_LIMITLESSLED_WHITE
            self._attr_effect_list = [EFFECT_NIGHT]
        elif isinstance(group, DimmerGroup):
            self._attr_supported_color_modes = COLOR_MODES_LIMITLESS_DIMMER
            self._attr_supported_features = SUPPORT_LIMITLESSLED_DIMMER
            self._attr_effect_list = []
        elif isinstance(group, RgbwGroup):
            self._attr_supported_color_modes = COLOR_MODES_LIMITLESS_RGB
            self._attr_supported_features = SUPPORT_LIMITLESSLED_RGB
            self._attr_effect_list = [EFFECT_COLORLOOP, EFFECT_NIGHT, EFFECT_WHITE]
        elif isinstance(group, RgbwwGroup):
            self._attr_supported_color_modes = COLOR_MODES_LIMITLESS_RGBWW
            self._attr_supported_features = SUPPORT_LIMITLESSLED_RGBWW
            self._attr_effect_list = [EFFECT_COLORLOOP, EFFECT_NIGHT, EFFECT_WHITE]

        self._fixed_color_mode = None
        if self.supported_color_modes and len(self.supported_color_modes) == 1:
            self._fixed_color_mode = next(iter(self.supported_color_modes))
        else:
            assert self._attr_supported_color_modes == {
                ColorMode.COLOR_TEMP,
                ColorMode.HS,
            }

        self.group = group
        self._attr_name = group.name
        self.config = config
        self._attr_is_on = False

    async def async_added_to_hass(self) -> None:
        """Handle entity about to be added to hass event."""
        await super().async_added_to_hass()
        if last_state := await self.async_get_last_state():
            self._attr_is_on = last_state.state == STATE_ON
            self._attr_brightness = last_state.attributes.get("brightness")
            self._attr_color_temp_kelvin = last_state.attributes.get(
                "color_temp_kelvin"
            )
            self._attr_hs_color = last_state.attributes.get("hs_color")

    @property
    def brightness(self) -> int | None:
        """Return the brightness property."""
        if self.effect == EFFECT_NIGHT:
            return 1

        return self._attr_brightness

    @property
    def color_mode(self) -> str | None:
        """Return the color mode of the light."""
        if self._fixed_color_mode:
            return self._fixed_color_mode

        # The light supports both hs and white with adjustable color temperature
        if (
            self.effect == EFFECT_NIGHT
            or self.hs_color is None
            or self.hs_color[1] == 0
        ):
            return ColorMode.COLOR_TEMP
        return ColorMode.HS

    @state(False)
    def turn_off(self, transition_time: int, pipeline: Pipeline, **kwargs: Any) -> None:
        """Turn off a group."""
        if self.config[CONF_FADE]:
            pipeline.transition(transition_time, brightness=0.0)
        pipeline.off()

    @state(True)
    def turn_on(self, transition_time: int, pipeline: Pipeline, **kwargs: Any) -> None:
        """Turn on (or adjust property of) a group."""
        # The night effect does not need a turned on light
        if kwargs.get(ATTR_EFFECT) == EFFECT_NIGHT:
            if self.effect_list and EFFECT_NIGHT in self.effect_list:
                pipeline.night_light()
                self._attr_effect = EFFECT_NIGHT
            return

        pipeline.on()

        # Set up transition.
        args = {}
        if self.config[CONF_FADE] and not self.is_on and self.brightness:
            args["brightness"] = self.limitlessled_brightness()

        if ATTR_BRIGHTNESS in kwargs:
            self._attr_brightness = kwargs[ATTR_BRIGHTNESS]
            args["brightness"] = self.limitlessled_brightness()

        if ATTR_HS_COLOR in kwargs:
            self._attr_hs_color = kwargs[ATTR_HS_COLOR]
            # White is a special case.
            assert self.hs_color is not None
            if self.hs_color[1] < MIN_SATURATION:
                pipeline.white()
                self._attr_hs_color = WHITE
            else:
                args["color"] = self.limitlessled_color()

        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            assert self.supported_color_modes
            if ColorMode.HS in self.supported_color_modes:
                pipeline.white()
            self._attr_hs_color = WHITE
            self._attr_color_temp_kelvin = kwargs[ATTR_COLOR_TEMP_KELVIN]
            args["temperature"] = self.limitlessled_temperature()

        if args:
            pipeline.transition(transition_time, **args)

        # Flash.
        if ATTR_FLASH in kwargs and self.supported_features & LightEntityFeature.FLASH:
            duration = 0
            if kwargs[ATTR_FLASH] == FLASH_LONG:
                duration = 1
            pipeline.flash(duration=duration)

        # Add effects.
        if ATTR_EFFECT in kwargs and self.effect_list:
            if kwargs[ATTR_EFFECT] == EFFECT_COLORLOOP:
                self._attr_effect = EFFECT_COLORLOOP
                pipeline.append(COLORLOOP)
            if kwargs[ATTR_EFFECT] == EFFECT_WHITE:
                pipeline.white()
                self._attr_hs_color = WHITE

    def limitlessled_temperature(self) -> float:
        """Convert Home Assistant color temperature units to percentage."""
        width = self.max_color_temp_kelvin - self.min_color_temp_kelvin
        assert self.color_temp_kelvin is not None
        temperature = (self.color_temp_kelvin - self.min_color_temp_kelvin) / width
        return max(0, min(1, temperature))

    def limitlessled_brightness(self) -> float:
        """Convert Home Assistant brightness units to percentage."""
        assert self.brightness is not None
        return self.brightness / 255

    def limitlessled_color(self) -> Color:
        """Convert Home Assistant HS list to RGB Color tuple."""
        assert self.hs_color is not None
        return Color(*color_hs_to_RGB(*self.hs_color))
