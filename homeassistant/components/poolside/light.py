"""Light platform for Poolside LIGHT controls."""

from typing import Any, override

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PoolsideConfigEntry
from .client import PoolsideClient
from .const import (
    BRIGHTNESS_FIELD,
    DEFAULT_COLOR_FIELD,
    LIGHT_NAME_FIELD,
    SPEED_FIELD,
    SUPPORTS_COLORS_FIELD,
    TWINKLE_FIELD,
    ControlType,
    StatusState,
)
from .entity import PoolsideEntity
from .models import PoolsideControl

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
        if control.control_type is ControlType.LIGHT
    )


class PoolsideLight(PoolsideEntity, LightEntity):
    """A LIGHT control.

    There is no RGB here: colored lights are driven by `LightName`, an opaque
    named color/light-show string from the site's installed palette, exposed
    as an HA effect. The controller can't tell us the full palette over this
    channel, only a `DefaultColor` - so the effect list is necessarily just
    that seeded with whatever LightName we've observed being set, not a
    complete catalog.

    Writes are full-state, not deltas: every write repeats Brightness, Speed,
    and Twinkle (and LightName, if colored), since any field left out is
    processed as 0 by the controller.
    """

    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS

    def __init__(self, client: PoolsideClient, control: PoolsideControl) -> None:
        """Set up the light, enabling the effect list if it supports color shows."""
        super().__init__(client, control)
        self._supports_color = bool(control.capability(SUPPORTS_COLORS_FIELD))
        self._default_color = control.capability(DEFAULT_COLOR_FIELD)
        if self._supports_color:
            self._attr_supported_features = LightEntityFeature.EFFECT

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
        value = self._desired(BRIGHTNESS_FIELD)
        if value is None:
            return None
        return round(float(value) / 100 * 255)

    @property
    @override
    def effect_list(self) -> list[str] | None:
        """Return the known named colors/light shows for this light."""
        if not self._supports_color:
            return None
        effects = {self._default_color} if self._default_color else set()
        if current := self._desired(LIGHT_NAME_FIELD):
            effects.add(current)
        return sorted(effects)

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
        if brightness is not None:
            brightness_percent = max(
                _MIN_BRIGHTNESS_PERCENT, round(brightness / 255 * 100)
            )
        else:
            brightness_percent = (
                max(_MIN_BRIGHTNESS_PERCENT, round(self.brightness / 255 * 100))
                if self.brightness
                else 100
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
