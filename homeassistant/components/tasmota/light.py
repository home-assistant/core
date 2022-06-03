"""Support for Tasmota lights."""
from __future__ import annotations

from typing import Any

from hatasmota import light as tasmota_light
from hatasmota.entity import TasmotaEntity as HATasmotaEntity, TasmotaEntityConfig
from hatasmota.light import (
    LIGHT_TYPE_COLDWARM,
    LIGHT_TYPE_NONE,
    LIGHT_TYPE_RGB,
    LIGHT_TYPE_RGBCW,
    LIGHT_TYPE_RGBW,
)
from hatasmota.models import DiscoveryHashType

from homeassistant.components import light
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    ATTR_WHITE,
    ColorMode,
    LightEntity,
    LightEntityFeature,
    brightness_supported,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_REMOVE_DISCOVER_COMPONENT
from .discovery import TASMOTA_DISCOVERY_ENTITY_NEW
from .mixins import TasmotaAvailability, TasmotaDiscoveryUpdate, TasmotaOnOffEntity

DEFAULT_BRIGHTNESS_MAX = 255
TASMOTA_BRIGHTNESS_MAX = 100


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tasmota light dynamically through discovery."""

    @callback
    def async_discover(
        tasmota_entity: HATasmotaEntity, discovery_hash: DiscoveryHashType
    ) -> None:
        """Discover and add a Tasmota light."""
        async_add_entities(
            [TasmotaLight(tasmota_entity=tasmota_entity, discovery_hash=discovery_hash)]
        )

    hass.data[
        DATA_REMOVE_DISCOVER_COMPONENT.format(light.DOMAIN)
    ] = async_dispatcher_connect(
        hass,
        TASMOTA_DISCOVERY_ENTITY_NEW.format(light.DOMAIN),
        async_discover,
    )


def clamp(value: float) -> float:
    """Clamp value to the range 0..255."""
    return min(max(value, 0), 255)


def scale_brightness(brightness: float) -> float:
    """Scale brightness from 0..255 to 1..100."""
    brightness_normalized = brightness / DEFAULT_BRIGHTNESS_MAX
    device_brightness = min(
        round(brightness_normalized * TASMOTA_BRIGHTNESS_MAX),
        TASMOTA_BRIGHTNESS_MAX,
    )
    # Make sure the brightness is not rounded down to 0
    return max(device_brightness, 1)


class TasmotaLight(
    TasmotaAvailability,
    TasmotaDiscoveryUpdate,
    TasmotaOnOffEntity,
    LightEntity,
):
    """Representation of a Tasmota light."""

    _tasmota_entity: tasmota_light.TasmotaLight

    def __init__(self, **kwds: Any) -> None:
        """Initialize Tasmota light."""
        self._supported_color_modes: set[str] | None = None

        self._brightness: int | None = None
        self._color_mode: str | None = None
        self._color_temp: int | None = None
        self._effect: str | None = None
        self._white_value: int | None = None
        self._flash_times = None
        self._hs: tuple[float, float] | None = None

        super().__init__(
            **kwds,
        )

        self._setup_from_entity()

    async def discovery_update(
        self, update: TasmotaEntityConfig, write_state: bool = True
    ) -> None:
        """Handle updated discovery message."""
        await super().discovery_update(update, write_state=False)
        self._setup_from_entity()
        self.async_write_ha_state()

    def _setup_from_entity(self) -> None:
        """(Re)Setup the entity."""
        self._supported_color_modes = set()
        supported_features = 0
        light_type = self._tasmota_entity.light_type

        if light_type in [LIGHT_TYPE_RGB, LIGHT_TYPE_RGBW, LIGHT_TYPE_RGBCW]:
            # Mark HS support for RGBW light because we don't have direct control over the
            # white channel, so the base component's RGB->RGBW translation does not work
            self._supported_color_modes.add(ColorMode.HS)
            self._color_mode = ColorMode.HS

        if light_type == LIGHT_TYPE_RGBW:
            self._supported_color_modes.add(ColorMode.WHITE)

        if light_type in [LIGHT_TYPE_COLDWARM, LIGHT_TYPE_RGBCW]:
            self._supported_color_modes.add(ColorMode.COLOR_TEMP)
            self._color_mode = ColorMode.COLOR_TEMP

        if light_type != LIGHT_TYPE_NONE and not self._supported_color_modes:
            self._supported_color_modes.add(ColorMode.BRIGHTNESS)
            self._color_mode = ColorMode.BRIGHTNESS

        if not self._supported_color_modes:
            self._supported_color_modes.add(ColorMode.ONOFF)
            self._color_mode = ColorMode.ONOFF

        if light_type in [LIGHT_TYPE_RGB, LIGHT_TYPE_RGBW, LIGHT_TYPE_RGBCW]:
            supported_features |= LightEntityFeature.EFFECT

        if self._tasmota_entity.supports_transition:
            supported_features |= LightEntityFeature.TRANSITION

        self._attr_supported_features = supported_features

    @callback
    def state_updated(self, state: bool, **kwargs: Any) -> None:
        """Handle state updates."""
        self._on_off_state = state
        if attributes := kwargs.get("attributes"):
            if "brightness" in attributes:
                brightness = float(attributes["brightness"])
                percent_bright = brightness / TASMOTA_BRIGHTNESS_MAX
                self._brightness = round(percent_bright * 255)
            if "color_hs" in attributes:
                self._hs = attributes["color_hs"]
            if "color_temp" in attributes:
                self._color_temp = attributes["color_temp"]
            if "effect" in attributes:
                self._effect = attributes["effect"]
            if "white_value" in attributes:
                white_value = float(attributes["white_value"])
                percent_white = white_value / TASMOTA_BRIGHTNESS_MAX
                self._white_value = round(percent_white * 255)
            if self._tasmota_entity.light_type == LIGHT_TYPE_RGBW:
                # Tasmota does not support RGBW mode, set mode to white or hs
                if self._white_value == 0:
                    self._color_mode = ColorMode.HS
                else:
                    self._color_mode = ColorMode.WHITE
            elif self._tasmota_entity.light_type == LIGHT_TYPE_RGBCW:
                # Tasmota does not support RGBWW mode, set mode to ct or hs
                if self._white_value == 0:
                    self._color_mode = ColorMode.HS
                else:
                    self._color_mode = ColorMode.COLOR_TEMP

        self.async_write_ha_state()

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def color_mode(self) -> str | None:
        """Return the color mode of the light."""
        return self._color_mode

    @property
    def color_temp(self) -> int | None:
        """Return the color temperature in mired."""
        return self._color_temp

    @property
    def min_mireds(self) -> int:
        """Return the coldest color_temp that this light supports."""
        return self._tasmota_entity.min_mireds

    @property
    def max_mireds(self) -> int:
        """Return the warmest color_temp that this light supports."""
        return self._tasmota_entity.max_mireds

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        return self._effect

    @property
    def effect_list(self) -> list[str] | None:
        """Return the list of supported effects."""
        return self._tasmota_entity.effect_list

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hs color value."""
        if self._hs is None:
            return None
        hs_color = self._hs
        return (hs_color[0], hs_color[1])

    @property
    def force_update(self) -> bool:
        """Force update."""
        return False

    @property
    def supported_color_modes(self) -> set[str] | None:
        """Flag supported color modes."""
        return self._supported_color_modes

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        supported_color_modes = self._supported_color_modes or set()

        attributes: dict[str, Any] = {}

        if ATTR_HS_COLOR in kwargs and ColorMode.HS in supported_color_modes:
            hs_color = kwargs[ATTR_HS_COLOR]
            attributes["color_hs"] = [hs_color[0], hs_color[1]]

        if ATTR_WHITE in kwargs and ColorMode.WHITE in supported_color_modes:
            attributes["white_value"] = scale_brightness(kwargs[ATTR_WHITE])

        if ATTR_TRANSITION in kwargs:
            attributes["transition"] = kwargs[ATTR_TRANSITION]

        if ATTR_BRIGHTNESS in kwargs and brightness_supported(supported_color_modes):
            attributes["brightness"] = scale_brightness(kwargs[ATTR_BRIGHTNESS])

        if ATTR_COLOR_TEMP in kwargs and ColorMode.COLOR_TEMP in supported_color_modes:
            attributes["color_temp"] = int(kwargs[ATTR_COLOR_TEMP])

        if ATTR_EFFECT in kwargs:
            attributes["effect"] = kwargs[ATTR_EFFECT]

        await self._tasmota_entity.set_state(True, attributes)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        attributes = {"state": "OFF"}

        if ATTR_TRANSITION in kwargs:
            attributes["transition"] = kwargs[ATTR_TRANSITION]

        await self._tasmota_entity.set_state(False, attributes)
