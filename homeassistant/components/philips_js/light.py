"""Component to integrate ambilight for TVs exposing the Joint Space API."""
from __future__ import annotations

from typing import Any

from haphilipsjs import PhilipsTV
from haphilipsjs.typing import AmbilightCurrentConfiguration

from homeassistant import config_entries
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    COLOR_MODE_HS,
    COLOR_MODE_ONOFF,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_EFFECT,
    LightEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.color import color_hsv_to_RGB, color_RGB_to_hsv

from . import PhilipsTVDataUpdateCoordinator
from .const import CONF_SYSTEM, DOMAIN

EFFECT_PARTITION = ": "
EFFECT_MODE = "Mode"
EFFECT_EXPERT = "Expert"
EFFECT_AUTO = "Auto"
EFFECT_EXPERT_STYLES = {"FOLLOW_AUDIO", "FOLLOW_COLOR", "Lounge light"}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Set up the configuration entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            PhilipsTVLightEntity(
                coordinator, config_entry.data[CONF_SYSTEM], config_entry.unique_id
            )
        ]
    )


def _get_settings(style: AmbilightCurrentConfiguration):
    """Extract the color settings data from a style."""
    if style["styleName"] in ("FOLLOW_COLOR", "Lounge light"):
        return style["colorSettings"]
    if style["styleName"] == "FOLLOW_AUDIO":
        return style["audioSettings"]
    return None


def _parse_effect(effect: str):
    style, _, algorithm = effect.partition(EFFECT_PARTITION)
    if style == EFFECT_MODE:
        return EFFECT_MODE, algorithm, None
    algorithm, _, expert = algorithm.partition(EFFECT_PARTITION)
    if expert:
        return EFFECT_EXPERT, style, algorithm
    return EFFECT_AUTO, style, algorithm


def _get_effect(mode: str, style: str, algorithm: str | None):
    if mode == EFFECT_MODE:
        return f"{EFFECT_MODE}{EFFECT_PARTITION}{style}"
    if mode == EFFECT_EXPERT:
        return f"{style}{EFFECT_PARTITION}{algorithm}{EFFECT_PARTITION}{EFFECT_EXPERT}"
    return f"{style}{EFFECT_PARTITION}{algorithm}"


def _is_on(mode, style, powerstate):
    if mode in (EFFECT_AUTO, EFFECT_EXPERT):
        if style in ("FOLLOW_VIDEO", "FOLLOW_AUDIO"):
            return powerstate in ("On", None)
        if style == "OFF":
            return False
        return True

    if mode == EFFECT_MODE:
        if style == "internal":
            return powerstate in ("On", None)
        return True

    return False


def _is_valid(mode, style):
    if mode == EFFECT_EXPERT:
        return style in EFFECT_EXPERT_STYLES
    return True


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


class PhilipsTVLightEntity(CoordinatorEntity, LightEntity):
    """Representation of a Philips TV exposing the JointSpace API."""

    def __init__(
        self,
        coordinator: PhilipsTVDataUpdateCoordinator,
        system: dict[str, Any],
        unique_id: str,
    ) -> None:
        """Initialize light."""
        self._tv = coordinator.api
        self._hs = None
        self._brightness = None
        self._system = system
        self._coordinator = coordinator
        self._cache_keys = None
        super().__init__(coordinator)

        self._attr_supported_color_modes = [COLOR_MODE_HS, COLOR_MODE_ONOFF]
        self._attr_supported_features = (
            SUPPORT_EFFECT | SUPPORT_COLOR | SUPPORT_BRIGHTNESS
        )
        self._attr_name = self._system["name"]
        self._attr_unique_id = unique_id
        self._attr_icon = "mdi:television-ambient-light"
        self._attr_device_info = {
            "name": self._system["name"],
            "identifiers": {
                (DOMAIN, self._attr_unique_id),
            },
            "model": self._system.get("model"),
            "manufacturer": "Philips",
            "sw_version": self._system.get("softwareversion"),
        }

        self._update_from_coordinator()

    def _calculate_effect_list(self):
        """Calculate an effect list based on current status."""
        effects = []
        effects.extend(
            _get_effect(EFFECT_AUTO, style, setting)
            for style, data in self._tv.ambilight_styles.items()
            if _is_valid(EFFECT_AUTO, style)
            and _is_on(EFFECT_AUTO, style, self._tv.powerstate)
            for setting in data.get("menuSettings", [])
        )

        effects.extend(
            _get_effect(EFFECT_EXPERT, style, algorithm)
            for style, data in self._tv.ambilight_styles.items()
            if _is_valid(EFFECT_EXPERT, style)
            and _is_on(EFFECT_EXPERT, style, self._tv.powerstate)
            for algorithm in data.get("algorithms", [])
        )

        effects.extend(
            _get_effect(EFFECT_MODE, style, None)
            for style in self._tv.ambilight_modes
            if _is_valid(EFFECT_MODE, style)
            and _is_on(EFFECT_MODE, style, self._tv.powerstate)
        )

        return sorted(effects)

    def _calculate_effect(self):
        """Return the current effect."""
        current = self._tv.ambilight_current_configuration
        if current and self._tv.ambilight_mode != "manual":
            if current["isExpert"]:
                settings = _get_settings(current)
                if settings:
                    return _get_effect(
                        EFFECT_EXPERT, current["styleName"], settings["algorithm"]
                    )
                return _get_effect(EFFECT_EXPERT, current["styleName"], None)

            return _get_effect(
                EFFECT_AUTO, current["styleName"], current.get("menuSetting", None)
            )

        return _get_effect(EFFECT_MODE, self._tv.ambilight_mode, None)

    @property
    def color_mode(self):
        """Return the current color mode."""
        current = self._tv.ambilight_current_configuration
        if current and current["isExpert"]:
            return COLOR_MODE_HS

        if self._tv.ambilight_mode in ["manual", "expert"]:
            return COLOR_MODE_HS

        return COLOR_MODE_ONOFF

    @property
    def is_on(self):
        """Return if the light is turned on."""
        if self._tv.on:
            mode, style, _ = _parse_effect(self.effect)
            return _is_on(mode, style, self._tv.powerstate)

        return False

    def _update_from_coordinator(self):
        current = self._tv.ambilight_current_configuration
        color = None

        if (cache_keys := _get_cache_keys(self._tv)) != self._cache_keys:
            self._cache_keys = cache_keys
            self._attr_effect_list = self._calculate_effect_list()
            self._attr_effect = self._calculate_effect()

        if current and current["isExpert"]:
            if settings := _get_settings(current):
                color = settings["color"]

        mode, _, _ = _parse_effect(self._attr_effect)

        if mode == EFFECT_EXPERT and color:
            self._attr_hs_color = (
                color["hue"] * 360.0 / 255.0,
                color["saturation"] * 100.0 / 255.0,
            )
            self._attr_brightness = color["brightness"]
        elif mode == EFFECT_MODE and self._tv.ambilight_cached:
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

    async def _set_ambilight_cached(self, algorithm, hs_color, brightness):
        """Set ambilight via the manual or expert mode."""
        rgb = color_hsv_to_RGB(hs_color[0], hs_color[1], brightness * 100 / 255)

        data = {
            "r": rgb[0],
            "g": rgb[1],
            "b": rgb[2],
        }

        if not await self._tv.setAmbilightCached(data):
            raise Exception("Failed to set ambilight color")

        if algorithm != self._tv.ambilight_mode:
            if not await self._tv.setAmbilightMode(algorithm):
                raise Exception("Failed to set ambilight mode")

    async def _set_ambilight_expert_config(
        self, style, algorithm, hs_color, brightness
    ):
        """Set ambilight via current configuration."""
        config: AmbilightCurrentConfiguration = {
            "styleName": style,
            "isExpert": True,
        }

        setting = {
            "algorithm": algorithm,
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

        if style in ("FOLLOW_COLOR", "Lounge light"):
            config["colorSettings"] = setting
            config["speed"] = 2

        elif style == "FOLLOW_AUDIO":
            config["audioSettings"] = setting
            config["tuning"] = 0

        if not await self._tv.setAmbilightCurrentConfiguration(config):
            raise Exception("Failed to set ambilight mode")

    async def _set_ambilight_config(self, style, algorithm):
        """Set ambilight via current configuration."""
        config: AmbilightCurrentConfiguration = {
            "styleName": style,
            "isExpert": False,
            "menuSetting": algorithm,
        }

        if await self._tv.setAmbilightCurrentConfiguration(config) is False:
            raise Exception("Failed to set ambilight mode")

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the bulb on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, self.brightness)
        hs_color = kwargs.get(ATTR_HS_COLOR, self.hs_color)
        effect = kwargs.get(ATTR_EFFECT, self.effect)

        if not self._tv.on:
            raise Exception("TV is not available")

        mode, style, setting = _parse_effect(effect)

        if not _is_on(mode, style, self._tv.powerstate):
            mode = EFFECT_MODE
            setting = None
            if self._tv.powerstate in ("On", None):
                style = "internal"
            else:
                style = "manual"

        if brightness is None:
            brightness = 255

        if hs_color is None:
            hs_color = [0, 0]

        if mode == EFFECT_MODE:
            await self._set_ambilight_cached(style, hs_color, brightness)
        elif mode == EFFECT_AUTO:
            await self._set_ambilight_config(style, setting)
        elif mode == EFFECT_EXPERT:
            await self._set_ambilight_expert_config(
                style, setting, hs_color, brightness
            )

        self._update_from_coordinator()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn of ambilight."""

        if not self._tv.on:
            raise Exception("TV is not available")

        if await self._tv.setAmbilightMode("internal") is False:
            raise Exception("Failed to set ambilight mode")

        await self._set_ambilight_config("OFF", "")

        self._update_from_coordinator()
        self.async_write_ha_state()
