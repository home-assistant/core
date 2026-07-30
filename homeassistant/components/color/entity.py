"""Entity class for the Color helper."""

import logging
from math import isfinite
from typing import Any, Self, override

from homeassistant.components import light
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ICON
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity

from .color_math import (
    CanonicalColor,
    ColorInputError,
    compute_source_hex,
    derive_hex,
    derive_hs,
    derive_kelvin,
    derive_rgb,
    normalize,
)
from .const import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_PARAMS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HEX_COLOR,
    ATTR_HS_COLOR,
    ATTR_KIND,
    ATTR_RGB_COLOR,
    ATTR_SOURCE_HEX,
    ATTR_XY_COLOR,
    CONF_INITIAL_BRIGHTNESS,
    CONF_INITIAL_COLOR,
    CONF_INITIAL_KELVIN,
    CONF_INITIAL_MODE,
    DEFAULT_HEX,
    DEFAULT_KELVIN,
    FIELD_HEX,
    FIELD_KELVIN,
    KIND_CHROMATIC,
    KIND_WHITE,
    MODE_WHITE,
    STATE_SCHEMA_VERSION,
)

_LOGGER = logging.getLogger(__name__)

type ColorConfigEntry = ConfigEntry[ColorEntity]


class _StoredColor(ExtraStoredData):
    """Restore payload preserving canonical precision across restarts."""

    def __init__(
        self,
        canonical: CanonicalColor,
        brightness: int | None,
        source_hex: str | None,
    ) -> None:
        """Initialize stored color data."""
        self.canonical = canonical
        self.brightness = brightness
        self.source_hex = source_hex

    @override
    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the stored color."""
        return {
            "brightness": self.brightness,
            "kelvin": self.canonical.kelvin,
            "kind": self.canonical.kind,
            "source_hex": self.source_hex,
            "version": STATE_SCHEMA_VERSION,
            "xy": list(self.canonical.xy),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self | None:
        """Create stored color data from a dict."""
        try:
            x, y = (float(value) for value in data["xy"])
            kind = str(data["kind"])
            canonical = CanonicalColor(
                xy=(x, y),
                kind=kind,
                kelvin=int(data["kelvin"]) if data.get("kelvin") is not None else None,
            )
            brightness = data.get("brightness")
            if brightness is not None:
                brightness = int(brightness)
            source_hex = data.get("source_hex")
            if source_hex is not None:
                source_hex = str(source_hex)
        except KeyError, TypeError, ValueError:
            return None
        if not (isfinite(x) and isfinite(y)) or kind not in (
            KIND_CHROMATIC,
            KIND_WHITE,
        ):
            return None
        return cls(canonical, brightness, source_hex)


class ColorEntity(RestoreEntity):
    """Represent a stored color value with derived representations."""

    _attr_should_poll = False
    _attr_has_entity_name = False

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
        self._source_hex = self._initial_source_hex(entry)

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
        except TypeError, ValueError:
            return None
        return max(0, min(255, value))

    @staticmethod
    def _initial_source_hex(entry: ColorConfigEntry) -> str | None:
        """Return the source hex for the initial color, if any."""
        if entry.data.get(CONF_INITIAL_MODE) == MODE_WHITE:
            return None
        initial = entry.data.get(CONF_INITIAL_COLOR)
        if not initial:
            return None
        return compute_source_hex({FIELD_HEX: initial})

    @property
    @override
    def state(self) -> str:
        """Return the state of the entity."""
        return derive_hex(self._canonical)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        x, y = self._canonical.xy
        r, g, b = derive_rgb(self._canonical)
        hue, sat = derive_hs(self._canonical)
        return {
            ATTR_BRIGHTNESS: self._brightness,
            ATTR_COLOR_PARAMS: self._color_params(),
            ATTR_COLOR_TEMP_KELVIN: derive_kelvin(self._canonical),
            ATTR_HEX_COLOR: derive_hex(self._canonical),
            ATTR_HS_COLOR: [round(hue, 2), round(sat, 2)],
            ATTR_KIND: self._canonical.kind,
            ATTR_RGB_COLOR: [r, g, b],
            ATTR_SOURCE_HEX: self._source_hex,
            ATTR_XY_COLOR: [round(x, 4), round(y, 4)],
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
        return _StoredColor(self._canonical, self._brightness, self._source_hex)

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
                self._source_hex = stored.source_hex

    async def async_set_color(self, **shape: Any) -> None:
        """Set the color from one accepted input shape."""
        color_shape = dict(shape)
        brightness = color_shape.pop(ATTR_BRIGHTNESS, None)
        self._canonical = normalize(color_shape)
        self._source_hex = compute_source_hex(color_shape)
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
