"""Component to integrate ambilight for TVs exposing the Joint Space API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from haphilipsjs import PhilipsTV
from haphilipsjs.typing import AmbilightCurrentConfiguration

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.color import color_hsv_to_RGB, color_RGB_to_hsv

from . import PhilipsTVDataUpdateCoordinator
from .const import DOMAIN
from .entity import PhilipsJsEntity

EFFECT_PARTITION = ": "
EFFECT_MODE = "Mode"
EFFECT_EXPERT = "Expert"
EFFECT_AUTO = "Auto"
EFFECT_EXPERT_STYLES = {"FOLLOW_AUDIO", "FOLLOW_COLOR", "Lounge light"}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the configuration entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([PhilipsTVLightEntity(coordinator)])


def _get_settings(style: AmbilightCurrentConfiguration):
    """Extract the color settings data from a style."""
    if style["styleName"] in ("FOLLOW_COLOR", "Lounge light"):
        return style["colorSettings"]
    if style["styleName"] == "FOLLOW_AUDIO":
        return style["audioSettings"]
    return None


@dataclass
class AmbilightEffect:
    """Data class describing the ambilight effect."""

    mode: str
    style: str
    algorithm: str | None = None

    def is_on(self, powerstate) -> bool:
        """Check whether the ambilight is considered on."""
        if self.mode in (EFFECT_AUTO, EFFECT_EXPERT):
            if self.style in ("FOLLOW_VIDEO", "FOLLOW_AUDIO"):
                return powerstate in ("On", None)
            if self.style == "OFF":
                return False
            return True

        if self.mode == EFFECT_MODE:
            if self.style == "internal":
                return powerstate in ("On", None)
            return True

        return False

    def is_valid(self) -> bool:
        """Validate the effect configuration."""
        if self.mode == EFFECT_EXPERT:
            return self.style in EFFECT_EXPERT_STYLES
        return True

    @staticmethod
    def from_str(effect_string: str) -> AmbilightEffect:
        """Create AmbilightEffect object from string."""
        style, _, algorithm = effect_string.partition(EFFECT_PARTITION)
        if style == EFFECT_MODE:
            return AmbilightEffect(mode=EFFECT_MODE, style=algorithm, algorithm=None)
        algorithm, _, expert = algorithm.partition(EFFECT_PARTITION)
        if expert:
            return AmbilightEffect(mode=EFFECT_EXPERT, style=style, algorithm=algorithm)
        return AmbilightEffect(mode=EFFECT_AUTO, style=style, algorithm=algorithm)

    def __str__(self) -> str:
        """Get a string representation of the effect."""
        if self.mode == EFFECT_MODE:
            return f"{EFFECT_MODE}{EFFECT_PARTITION}{self.style}"
        if self.mode == EFFECT_EXPERT:
            return f"{self.style}{EFFECT_PARTITION}{self.algorithm}{EFFECT_PARTITION}{EFFECT_EXPERT}"
        return f"{self.style}{EFFECT_PARTITION}{self.algorithm}"


def _get_cache_keys(device: PhilipsTV):
    """Return a cache keys to avoid always updating."""
    return (
        device.on,
        device.powerstate,
        device.ambilight_current_configuration,
        device.ambilight_mode,
    )


def _average_pixels(data):
    """Calculate an average color over all ambilight pixels."""
    color_c = 0
    color_r = 0.0
    color_g = 0.0
    color_b = 0.0
    for layer in data.values():
        for side in layer.values():
            for pixel in side.values():
                color_c += 1
                color_r += pixel["r"]
                color_g += pixel["g"]
                color_b += pixel["b"]

    if color_c:
        color_r /= color_c
        color_g /= color_c
        color_b /= color_c
        return color_r, color_g, color_b
    return 0.0, 0.0, 0.0


class PhilipsTVLightEntity(PhilipsJsEntity, LightEntity):
    """Representation of a Philips TV exposing the JointSpace API."""

    _attr_translation_key = "ambilight"

    def __init__(
        self,
        coordinator: PhilipsTVDataUpdateCoordinator,
    ) -> None:
        """Initialize light."""
        self._tv = coordinator.api
        self._hs = None
        self._brightness = None
        self._cache_keys = None
        self._last_selected_effect: AmbilightEffect | None = None
        super().__init__(coordinator)

        self._attr_supported_color_modes = {ColorMode.HS, ColorMode.ONOFF}
        self._attr_supported_features = LightEntityFeature.EFFECT
        self._attr_unique_id = coordinator.unique_id

        self._update_from_coordinator()

    def _calculate_effect_list(self):
        """Calculate an effect list based on current status."""
        effects: list[AmbilightEffect] = []
        effects.extend(
            AmbilightEffect(mode=EFFECT_AUTO, style=style, algorithm=setting)
            for style, data in self._tv.ambilight_styles.items()
            for setting in data.get("menuSettings", [])
        )

        effects.extend(
            AmbilightEffect(mode=EFFECT_EXPERT, style=style, algorithm=algorithm)
            for style, data in self._tv.ambilight_styles.items()
            for algorithm in data.get("algorithms", [])
        )

        effects.extend(
            AmbilightEffect(mode=EFFECT_MODE, style=style)
            for style in self._tv.ambilight_modes
        )

        filtered_effects = [
            str(effect)
            for effect in effects
            if effect.is_valid() and effect.is_on(self._tv.powerstate)
        ]

        return sorted(filtered_effects)

    def _calculate_effect(self) -> AmbilightEffect:
        """Return the current effect."""
        current = self._tv.ambilight_current_configuration
        if current and self._tv.ambilight_mode != "manual":
            if current["isExpert"]:
                if settings := _get_settings(current):
                    return AmbilightEffect(
                        EFFECT_EXPERT, current["styleName"], settings["algorithm"]
                    )
                return AmbilightEffect(EFFECT_EXPERT, current["styleName"], None)

            return AmbilightEffect(
                EFFECT_AUTO, current["styleName"], current.get("menuSetting", None)
            )

        return AmbilightEffect(EFFECT_MODE, self._tv.ambilight_mode, None)

    @property
    def color_mode(self) -> ColorMode:
        """Return the current color mode."""
        current = self._tv.ambilight_current_configuration
        if current and current["isExpert"]:
            return ColorMode.HS

        if self._tv.ambilight_mode in ["manual", "expert"]:
            return ColorMode.HS

        return ColorMode.ONOFF

    @property
    def is_on(self):
        """Return if the light is turned on."""
        if self._tv.on:
            effect = AmbilightEffect.from_str(self.effect)
            return effect.is_on(self._tv.powerstate)

        return False

    def _update_from_coordinator(self):
        current = self._tv.ambilight_current_configuration
        color = None

        if (cache_keys := _get_cache_keys(self._tv)) != self._cache_keys:
            self._cache_keys = cache_keys
            self._attr_effect_list = self._calculate_effect_list()
            self._attr_effect = str(self._calculate_effect())

        if current and current["isExpert"]:
            if settings := _get_settings(current):
                color = settings["color"]

        effect = AmbilightEffect.from_str(self._attr_effect)
        if effect.is_on(self._tv.powerstate):
            self._last_selected_effect = effect

        if effect.mode == EFFECT_EXPERT and color:
            self._attr_hs_color = (
                color["hue"] * 360.0 / 255.0,
                color["saturation"] * 100.0 / 255.0,
            )
            self._attr_brightness = color["brightness"]
        elif effect.mode == EFFECT_MODE and self._tv.ambilight_cached:
            hsv_h, hsv_s, hsv_v = color_RGB_to_hsv(
                *_average_pixels(self._tv.ambilight_cached)
            )
            self._attr_hs_color = hsv_h, hsv_s
            self._attr_brightness = hsv_v * 255.0 / 100.0
        else:
            self._attr_hs_color = None
            self._attr_brightness = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_from_coordinator()
        super()._handle_coordinator_update()

    async def _set_ambilight_cached(
        self, effect: AmbilightEffect, hs_color: tuple[float, float], brightness: int
    ):
        """Set ambilight via the manual or expert mode."""
        rgb = color_hsv_to_RGB(hs_color[0], hs_color[1], brightness * 100 / 255)

        data = {
            "r": rgb[0],
            "g": rgb[1],
            "b": rgb[2],
        }

        if not await self._tv.setAmbilightCached(data):
            raise HomeAssistantError("Failed to set ambilight color")

        if effect.style != self._tv.ambilight_mode:
            if not await self._tv.setAmbilightMode(effect.style):
                raise HomeAssistantError("Failed to set ambilight mode")

    async def _set_ambilight_expert_config(
        self, effect: AmbilightEffect, hs_color: tuple[float, float], brightness: int
    ):
        """Set ambilight via current configuration."""
        config: AmbilightCurrentConfiguration = {
            "styleName": effect.style,
            "isExpert": True,
        }

        setting = {
            "algorithm": effect.algorithm,
            "color": {
                "hue": round(hs_color[0] * 255.0 / 360.0),
                "saturation": round(hs_color[1] * 255.0 / 100.0),
                "brightness": round(brightness),
            },
            "colorDelta": {
                "hue": 0,
                "saturation": 0,
                "brightness": 0,
            },
        }

        if effect.style in ("FOLLOW_COLOR", "Lounge light"):
            config["colorSettings"] = setting
            config["speed"] = 2

        elif effect.style == "FOLLOW_AUDIO":
            config["audioSettings"] = setting
            config["tuning"] = 0

        if not await self._tv.setAmbilightCurrentConfiguration(config):
            raise HomeAssistantError("Failed to set ambilight mode")

    async def _set_ambilight_config(self, effect: AmbilightEffect):
        """Set ambilight via current configuration."""
        config: AmbilightCurrentConfiguration = {
            "styleName": effect.style,
            "isExpert": False,
            "menuSetting": effect.algorithm,
        }

        if await self._tv.setAmbilightCurrentConfiguration(config) is False:
            raise HomeAssistantError("Failed to set ambilight mode")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the bulb on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, self.brightness)
        hs_color = kwargs.get(ATTR_HS_COLOR, self.hs_color)
        attr_effect = kwargs.get(ATTR_EFFECT, self.effect)

        if not self._tv.on:
            raise HomeAssistantError("TV is not available")

        effect = AmbilightEffect.from_str(attr_effect)

        if effect.style == "OFF":
            if self._last_selected_effect:
                effect = self._last_selected_effect
            else:
                effect = AmbilightEffect(EFFECT_AUTO, "FOLLOW_VIDEO", "STANDARD")

        if not effect.is_on(self._tv.powerstate):
            effect.mode = EFFECT_MODE
            effect.algorithm = None
            if self._tv.powerstate in ("On", None):
                effect.style = "internal"
            else:
                effect.style = "manual"

        if brightness is None:
            brightness = 255

        if hs_color is None:
            hs_color = (0, 0)

        if effect.mode == EFFECT_MODE:
            await self._set_ambilight_cached(effect, hs_color, brightness)
        elif effect.mode == EFFECT_AUTO:
            await self._set_ambilight_config(effect)
        elif effect.mode == EFFECT_EXPERT:
            await self._set_ambilight_expert_config(effect, hs_color, brightness)

        self._update_from_coordinator()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn of ambilight."""

        if not self._tv.on:
            raise HomeAssistantError("TV is not available")

        if await self._tv.setAmbilightMode("internal") is False:
            raise HomeAssistantError("Failed to set ambilight mode")

        await self._set_ambilight_config(AmbilightEffect(EFFECT_MODE, "OFF", ""))

        self._update_from_coordinator()
        self.async_write_ha_state()
