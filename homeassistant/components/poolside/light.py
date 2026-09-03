"""Light platform for Poolside LIGHT controls."""

from typing import Any, override

from aiopoolside import PoolsideClient, PoolsideControl
from aiopoolside.const import (
    AVAILABLE_COLORS_FIELD,
    AVAILABLE_SHOWS_FIELD,
    BRIGHTNESS_FIELD,
    BRIGHTNESS_INCREMENTS_FIELD,
    DEFAULT_COLOR_FIELD,
    LIGHT_NAME_FIELD,
    SPEED_FIELD,
    SUPPORTS_BRIGHTNESS_FIELD,
    SUPPORTS_COLORS_FIELD,
    TWINKLE_FIELD,
    StatusState,
)

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PoolsideConfigEntry
from .entity import PoolsideEntity, control_platform

# The controller coerces a written Brightness <= 0 to 100 rather than off;
# never send 0 while turning/keeping a light on.
_MIN_BRIGHTNESS_PERCENT = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PoolsideConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Poolside light entities."""
    data = entry.runtime_data
    async_add_entities(
        PoolsideLight(data.client, control)
        for control in data.controls
        if control_platform(control) is Platform.LIGHT
    )


class PoolsideLight(PoolsideEntity, LightEntity):
    """A LIGHT control.

    There is no RGB here: colored lights are driven by `LightName`, an opaque
    named color or light-show string, exposed as an HA effect. The full
    catalog of choices is the union of two controller-pushed lists -
    `AvailableShows` (multi-color patterns like "Party Mode") and
    `AvailableColors` (static colors like "Blue") - since both are valid
    values to write back as `LightName`.

    Dimming is governed by two controller-pushed capabilities:
    `SupportsBrightness` (false means the light is plain on/off, though it
    may still take color selection) and `BrightnessIncrements`, the exact
    Brightness percent levels the hardware accepts (e.g. only quarters) -
    requested brightness is snapped to the nearest allowed level.

    Writes are full-state, not deltas: every write repeats Brightness, Speed,
    and Twinkle (and LightName, if colored), since any field left out is
    processed as 0 by the controller.
    """

    def __init__(self, client: PoolsideClient, control: PoolsideControl) -> None:
        """Set up the light, enabling the effect list if it supports color shows."""
        super().__init__(client, control)
        self._supports_color = bool(control.capability(SUPPORTS_COLORS_FIELD))
        self._default_color = control.capability(DEFAULT_COLOR_FIELD)
        if self._supports_color:
            self._attr_supported_features = LightEntityFeature.EFFECT

    def _supports_brightness(self) -> bool:
        """Return whether the light is dimmable, assuming yes until told otherwise."""
        return self._confirmed_json(SUPPORTS_BRIGHTNESS_FIELD) is not False

    def _brightness_increments(self) -> list[int]:
        """Return the Brightness percent levels the hardware accepts, if constrained."""
        value = self._confirmed_json(BRIGHTNESS_INCREMENTS_FIELD)
        if not isinstance(value, list):
            return []
        return [level for level in value if isinstance(level, int) and 0 < level <= 100]

    @property
    @override
    def supported_color_modes(self) -> set[ColorMode]:
        """Return brightness support, falling back to plain on/off."""
        if self._supports_brightness():
            return {ColorMode.BRIGHTNESS}
        return {ColorMode.ONOFF}

    @property
    @override
    def color_mode(self) -> ColorMode:
        """Return the light's current color mode."""
        if self._supports_brightness():
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the light is on."""
        status = self._power_state()
        if status is None:
            return None
        return status == StatusState.ON

    @property
    @override
    def brightness(self) -> int | None:
        """Return the light's brightness, converted from the device's 0-100 scale."""
        if not self._supports_brightness():
            return None
        value = self._desired(BRIGHTNESS_FIELD)
        if value is None:
            return None
        return round(float(value) / 100 * 255)

    def _catalog(self, field: str) -> set[str]:
        """Return one of the controller's named-show/color catalog lists."""
        value = self._confirmed_json(field)
        if not isinstance(value, list):
            return set()
        return {item for item in value if isinstance(item, str)}

    @property
    @override
    def effect_list(self) -> list[str] | None:
        """Return the controller's catalog of named shows and static colors."""
        if not self._supports_color:
            return None
        catalog = self._catalog(AVAILABLE_SHOWS_FIELD) | self._catalog(
            AVAILABLE_COLORS_FIELD
        )
        return sorted(catalog) or None

    @property
    @override
    def effect(self) -> str | None:
        """Return the light's current named color/light show."""
        if not self._supports_color:
            return None
        return self._desired(LIGHT_NAME_FIELD)

    def _current_speed(self) -> str:
        return str(self._desired(SPEED_FIELD) or 0)

    def _current_twinkle(self) -> str:
        return str(self._desired(TWINKLE_FIELD) or 0)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on, writing its complete state (brightness/speed/twinkle/color)."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if not self._supports_brightness():
            brightness_percent = 100
        elif brightness is not None:
            brightness_percent = max(
                _MIN_BRIGHTNESS_PERCENT, round(brightness / 255 * 100)
            )
        else:
            brightness_percent = (
                max(_MIN_BRIGHTNESS_PERCENT, round(self.brightness / 255 * 100))
                if self.brightness
                else 100
            )
        if increments := self._brightness_increments():
            brightness_percent = min(
                increments, key=lambda level: abs(level - brightness_percent)
            )

        fields: dict[str, Any] = {
            "Status": StatusState.ON.value,
            BRIGHTNESS_FIELD: str(brightness_percent),
            SPEED_FIELD: self._current_speed(),
            TWINKLE_FIELD: self._current_twinkle(),
        }
        if self._supports_color:
            effect = kwargs.get(ATTR_EFFECT) or self.effect or self._default_color
            if effect is not None:
                fields[LIGHT_NAME_FIELD] = effect

        await self._async_write_state(**fields)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._async_write_state(Status=StatusState.OFF.value)
