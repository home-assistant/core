"""Entity class for the Color helper."""

import logging
from typing import Any, Self, override

from homeassistant.components import light
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ICON
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity

from .color_math import (
    CanonicalColor,
    ColorInputError,
    derive_hex,
    derive_hs,
    derive_kelvin,
    derive_rgb,
    normalize,
    valid_xy,
)
from .const import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_PARAMS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HEX_COLOR,
    ATTR_HS_COLOR,
    ATTR_KIND,
    ATTR_RGB_COLOR,
    ATTR_XY_COLOR,
    CONF_INITIAL_BRIGHTNESS,
    CONF_INITIAL_COLOR,
    CONF_INITIAL_KELVIN,
    CONF_INITIAL_MODE,
    DEFAULT_HEX,
    DEFAULT_KELVIN,
    FIELD_HEX,
    FIELD_HS,
    FIELD_KELVIN,
    FIELD_XY,
    KIND_CHROMATIC,
    KIND_WHITE,
    MAX_KELVIN,
    MIN_KELVIN,
    MODE_WHITE,
    STATE_SCHEMA_VERSION,
)

_LOGGER = logging.getLogger(__name__)

type ColorConfigEntry = ConfigEntry[ColorEntity]


class _StoredColor(ExtraStoredData):
    """Restore payload preserving canonical precision across restarts."""

    def __init__(self, canonical: CanonicalColor, brightness: int | None) -> None:
        """Initialize stored color data."""
        self.canonical = canonical
        self.brightness = brightness

    @override
    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the stored color."""
        source_value = self.canonical.source_value
        return {
            "brightness": self.brightness,
            "kelvin": self.canonical.kelvin,
            "kind": self.canonical.kind,
            "source_field": self.canonical.source_field,
            "source_value": list(source_value)
            if isinstance(source_value, tuple)
            else source_value,
            "version": STATE_SCHEMA_VERSION,
            "xy": list(self.canonical.xy),
        }

    @staticmethod
    def _restored_canonical(
        data: dict[str, Any],
        version: int,
        x: float,
        y: float,
        kind: str,
        kelvin: int | None,
    ) -> CanonicalColor:
        """Rebuild the canonical color, preferring the stored exact source.

        A malformed source only costs the exact-input echo, so fall back to
        the canonical xy/kelvin rather than rejecting an otherwise-restorable
        color.
        """
        if version == 1:
            # v1 stored the sRGB inputs' normalized hex as source_hex.
            source = {FIELD_HEX: data.get("source_hex")}
        else:
            source = {str(data.get("source_field")): data.get("source_value")}
        try:
            canonical = normalize(source)
        except ColorInputError:
            canonical = None
        if canonical is not None and canonical.kind == kind:
            return canonical
        if kind == KIND_WHITE:
            return normalize({FIELD_KELVIN: kelvin})
        return normalize({FIELD_XY: [x, y]})

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self | None:
        """Create stored color data from a dict."""
        try:
            version = int(data["version"])
            x, y = (float(value) for value in data["xy"])
            kind = str(data["kind"])
            kelvin = int(data["kelvin"]) if data.get("kelvin") is not None else None
            brightness = data.get("brightness")
            if brightness is not None:
                brightness = int(brightness)
        except KeyError, TypeError, ValueError, OverflowError:
            return None
        if (
            version not in (1, STATE_SCHEMA_VERSION)
            or not valid_xy(x, y)
            or kind not in (KIND_CHROMATIC, KIND_WHITE)
            or (
                kind == KIND_WHITE
                and (kelvin is None or not MIN_KELVIN <= kelvin <= MAX_KELVIN)
            )
            or (kind == KIND_CHROMATIC and kelvin is not None)
            or (brightness is not None and not 0 <= brightness <= 255)
        ):
            return None
        return cls(
            cls._restored_canonical(data, version, x, y, kind, kelvin), brightness
        )


class ColorEntity(RestoreEntity):
    """Represent a stored color value with derived representations."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    # Derived views of the canonical value; recording them just duplicates
    # the state string in the database.
    _unrecorded_attributes = frozenset(
        {
            ATTR_COLOR_PARAMS,
            ATTR_HEX_COLOR,
            ATTR_HS_COLOR,
            ATTR_RGB_COLOR,
            ATTR_XY_COLOR,
        }
    )

    def __init__(self, entry: ColorConfigEntry) -> None:
        """Initialize the color entity from its config entry."""
        self._entry = entry
        self._attr_unique_id = entry.entry_id
        # The update listener reloads the entry on rename/options change, so
        # name and icon can be set once here.
        self._attr_name = entry.title
        # Options (which store None for "cleared") win over the creation icon.
        if CONF_ICON in entry.options:
            self._attr_icon = entry.options[CONF_ICON]
        else:
            self._attr_icon = entry.data.get(CONF_ICON)
        self._canonical = self._initial_canonical(entry)
        self._brightness = self._initial_brightness(entry)

    @staticmethod
    def _initial_canonical(entry: ColorConfigEntry) -> CanonicalColor:
        """Return the initial canonical color."""
        if entry.data.get(CONF_INITIAL_MODE) == MODE_WHITE:
            kelvin = entry.data.get(CONF_INITIAL_KELVIN, DEFAULT_KELVIN)
            try:
                return normalize({FIELD_KELVIN: kelvin})
            except ColorInputError:
                return normalize({FIELD_KELVIN: DEFAULT_KELVIN})

        initial = entry.data.get(CONF_INITIAL_COLOR, DEFAULT_HEX)
        try:
            return normalize({FIELD_HEX: initial})
        except ColorInputError:
            return normalize({FIELD_HEX: DEFAULT_HEX})

    @staticmethod
    def _initial_brightness(entry: ColorConfigEntry) -> int | None:
        """Return the initial brightness."""
        brightness = entry.data.get(CONF_INITIAL_BRIGHTNESS)
        if brightness is None:
            return None
        try:
            value = int(brightness)
        except TypeError, ValueError, OverflowError:
            return None
        return max(0, min(255, value))

    @property
    @override
    def state(self) -> str:
        """Return the state of the entity."""
        return derive_hex(self._canonical)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        canonical = self._canonical
        x, y = canonical.xy
        r, g, b = derive_rgb(canonical)
        hue, sat = derive_hs(canonical)
        # Rounding applies only to derived views; the shape the user set is
        # echoed exactly as given.
        return {
            ATTR_BRIGHTNESS: self._brightness,
            ATTR_COLOR_PARAMS: self._color_params(),
            ATTR_COLOR_TEMP_KELVIN: derive_kelvin(canonical),
            ATTR_HEX_COLOR: derive_hex(canonical),
            ATTR_HS_COLOR: [hue, sat]
            if canonical.source_field == FIELD_HS
            else [round(hue, 2), round(sat, 2)],
            ATTR_KIND: canonical.kind,
            ATTR_RGB_COLOR: [r, g, b],
            ATTR_XY_COLOR: [x, y]
            if canonical.source_field == FIELD_XY
            else [round(x, 4), round(y, 4)],
        }

    def _color_params(self) -> dict[str, Any]:
        """Return a payload splattable directly into light.turn_on."""
        if self._canonical.kind == KIND_WHITE and self._canonical.kelvin is not None:
            params: dict[str, Any] = {
                light.ATTR_COLOR_TEMP_KELVIN: self._canonical.kelvin
            }
        else:
            x, y = self._canonical.xy
            params = {light.ATTR_XY_COLOR: [x, y]}
        if self._brightness is not None:
            params[light.ATTR_BRIGHTNESS] = self._brightness
        return params

    @property
    @override
    def extra_restore_state_data(self) -> ExtraStoredData | None:
        """Return entity data to restore."""
        return _StoredColor(self._canonical, self._brightness)

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the stored color when the entity is added."""
        await super().async_added_to_hass()
        last_extra = await self.async_get_last_extra_data()
        if last_extra is not None:
            stored = _StoredColor.from_dict(last_extra.as_dict())
            if stored is not None:
                self._canonical = stored.canonical
                self._brightness = stored.brightness

    async def async_set_color(self, **shape: Any) -> None:
        """Set the color from one accepted input shape."""
        color_shape = dict(shape)
        brightness = color_shape.pop(ATTR_BRIGHTNESS, None)
        self._canonical = normalize(color_shape)
        if brightness is not None:
            self._brightness = max(0, min(255, int(brightness)))
        self.async_write_ha_state()

    async def async_set_brightness(self, brightness: int | None) -> None:
        """Set or clear the stored brightness."""
        if brightness is None:
            self._brightness = None
        else:
            self._brightness = max(0, min(255, int(brightness)))
        self.async_write_ha_state()
