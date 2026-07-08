"""Entity support for the input color helper."""

from typing import Any, Self, override

from homeassistant.const import ATTR_EDITABLE, CONF_ICON, CONF_ID, CONF_NAME
from homeassistant.helpers import collection
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.helpers.typing import ConfigType

from . import (
    ATTR_BRIGHTNESS,
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
    DEFAULT_HEX,
    DOMAIN,
    STATE_SCHEMA_VERSION,
)
from .color_math import (
    FIELD_HEX,
    FIELD_KELVIN,
    CanonicalColor,
    compute_source_hex,
    derive_hex,
    derive_hs,
    derive_kelvin,
    derive_rgb,
    normalize,
)


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
            "kind": self.canonical.kind,
            "kelvin": self.canonical.kelvin,
            "source_hex": self.source_hex,
            "version": STATE_SCHEMA_VERSION,
            "xy": list(self.canonical.xy),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> _StoredColor | None:
        """Create stored color data from a dict."""
        try:
            xy = data["xy"]
            canonical = CanonicalColor(
                xy=(float(xy[0]), float(xy[1])),
                kind=str(data["kind"]),
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
        return cls(canonical, brightness, source_hex)


class InputColor(collection.CollectionEntity, RestoreEntity):
    """Represent a stored color value."""

    _unrecorded_attributes = frozenset({ATTR_EDITABLE})

    _attr_should_poll = False
    editable: bool

    def __init__(self, config: ConfigType) -> None:
        """Initialize an input color."""
        self._config = config
        self._canonical = self._initial_canonical(config)
        self._brightness = self._initial_brightness(config)
        self._source_hex = self._initial_source_hex(config)

    @classmethod
    @override
    def from_storage(cls, config: ConfigType) -> Self:
        """Return entity instance initialized from storage."""
        input_color = cls(config)
        input_color.editable = True
        return input_color

    @classmethod
    @override
    def from_yaml(cls, config: ConfigType) -> Self:
        """Return entity instance initialized from yaml."""
        input_color = cls(config)
        input_color.entity_id = f"{DOMAIN}.{config[CONF_ID]}"
        input_color.editable = False
        return input_color

    @staticmethod
    def _initial_canonical(config: ConfigType) -> CanonicalColor:
        """Return the initial canonical color."""
        if CONF_INITIAL_KELVIN in config:
            return normalize({FIELD_KELVIN: config[CONF_INITIAL_KELVIN]})
        return normalize({FIELD_HEX: config.get(CONF_INITIAL_COLOR, DEFAULT_HEX)})

    @staticmethod
    def _initial_brightness(config: ConfigType) -> int | None:
        """Return initial brightness."""
        brightness = config.get(CONF_INITIAL_BRIGHTNESS)
        if brightness is None:
            return None
        return max(0, min(255, int(brightness)))

    @staticmethod
    def _initial_source_hex(config: ConfigType) -> str | None:
        """Return source hex for the initial color."""
        if CONF_INITIAL_KELVIN in config:
            return None
        initial_color = config.get(CONF_INITIAL_COLOR)
        if initial_color is None:
            return compute_source_hex({FIELD_HEX: DEFAULT_HEX})
        return compute_source_hex({FIELD_HEX: initial_color})

    @property
    @override
    def name(self) -> str | None:
        """Return the name of the color input entity."""
        return self._config.get(CONF_NAME)

    @property
    @override
    def icon(self) -> str | None:
        """Return the icon to be used for this entity."""
        return self._config.get(CONF_ICON)

    @property
    @override
    def state(self) -> str:
        """Return the state of the entity."""
        return self._source_hex or derive_hex(self._canonical)

    @property
    @override
    def unique_id(self) -> str:
        """Return unique id for the entity."""
        return self._config[CONF_ID]

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        x, y = self._canonical.xy
        r, g, b = derive_rgb(self._canonical)
        h, s = derive_hs(self._canonical)
        return {
            ATTR_BRIGHTNESS: self._brightness,
            ATTR_COLOR_TEMP_KELVIN: derive_kelvin(self._canonical),
            ATTR_EDITABLE: self.editable,
            ATTR_HEX_COLOR: self.state,
            ATTR_HS_COLOR: [round(h, 2), round(s, 2)],
            ATTR_KIND: self._canonical.kind,
            ATTR_RGB_COLOR: [r, g, b],
            ATTR_SOURCE_HEX: self._source_hex,
            ATTR_XY_COLOR: [round(x, 4), round(y, 4)],
        }

    @property
    @override
    def extra_restore_state_data(self) -> ExtraStoredData | None:
        """Return entity data to restore."""
        return _StoredColor(self._canonical, self._brightness, self._source_hex)

    @override
    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        if (
            self._config.get(CONF_INITIAL_COLOR) is not None
            or self._config.get(CONF_INITIAL_KELVIN) is not None
        ):
            return

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

    @override
    async def async_update_config(self, config: ConfigType) -> None:
        """Handle when the config is updated."""
        self._config = config
        self.async_write_ha_state()
