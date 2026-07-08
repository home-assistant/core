"""Support to store reusable color values."""

import logging
from typing import Any, Self, override

import voluptuous as vol

from homeassistant.const import (
    ATTR_EDITABLE,
    CONF_ICON,
    CONF_ID,
    CONF_NAME,
    SERVICE_RELOAD,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import collection, config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
import homeassistant.helpers.service
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType, VolDictType

from .color_math import (
    FIELD_COLOR_NAME,
    FIELD_HEX,
    FIELD_HS,
    FIELD_KELVIN,
    FIELD_RGB,
    FIELD_XY,
    MAX_KELVIN,
    MIN_KELVIN,
    CanonicalColor,
    ColorInputError,
    compute_source_hex,
    derive_hex,
    derive_hs,
    derive_kelvin,
    derive_rgb,
    normalize,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "input_color"

CONF_INITIAL_BRIGHTNESS = "initial_brightness"
CONF_INITIAL_COLOR = "initial_color"
CONF_INITIAL_KELVIN = "initial_kelvin"

ATTR_BRIGHTNESS = "brightness"
ATTR_COLOR_TEMP_KELVIN = "color_temp_kelvin"
ATTR_HEX_COLOR = "hex_color"
ATTR_HS_COLOR = "hs_color"
ATTR_KIND = "kind"
ATTR_RGB_COLOR = "rgb_color"
ATTR_SOURCE_HEX = "source_hex"
ATTR_XY_COLOR = "xy_color"

DEFAULT_HEX = "#FFFFFF"
DEFAULT_KELVIN = 4000

SERVICE_CLEAR_BRIGHTNESS = "clear_brightness"
SERVICE_SET_BRIGHTNESS = "set_brightness"
SERVICE_SET_COLOR = "set_color"

STATE_SCHEMA_VERSION = 1
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

STORAGE_FIELDS: VolDictType = {
    vol.Required(CONF_NAME): vol.All(str, vol.Length(min=1)),
    vol.Optional(CONF_INITIAL_COLOR): cv.string,
    vol.Optional(CONF_INITIAL_KELVIN): vol.All(
        vol.Coerce(int), vol.Range(min=MIN_KELVIN, max=MAX_KELVIN)
    ),
    vol.Optional(CONF_INITIAL_BRIGHTNESS): vol.All(
        vol.Coerce(int), vol.Range(min=0, max=255)
    ),
    vol.Optional(CONF_ICON): cv.icon,
}


def _cv_input_color(config: dict[str, Any]) -> dict[str, Any]:
    """Validate input color configuration."""
    has_color = config.get(CONF_INITIAL_COLOR) is not None
    has_kelvin = config.get(CONF_INITIAL_KELVIN) is not None
    if has_color and has_kelvin:
        raise vol.Invalid("Only one of initial_color or initial_kelvin is allowed")
    if has_color:
        try:
            normalize({FIELD_HEX: config[CONF_INITIAL_COLOR]})
        except ColorInputError as err:
            raise vol.Invalid(str(err)) from err
    return config


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: cv.schema_with_slug_keys(
            vol.All(
                lambda value: value or {},
                {
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Optional(CONF_INITIAL_COLOR): cv.string,
                    vol.Optional(CONF_INITIAL_KELVIN): vol.All(
                        vol.Coerce(int), vol.Range(min=MIN_KELVIN, max=MAX_KELVIN)
                    ),
                    vol.Optional(CONF_INITIAL_BRIGHTNESS): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=255)
                    ),
                    vol.Optional(CONF_ICON): cv.icon,
                },
                _cv_input_color,
            )
        )
    },
    extra=vol.ALLOW_EXTRA,
)

RELOAD_SERVICE_SCHEMA = vol.Schema({})

SET_COLOR_SCHEMA = {
    vol.Optional(FIELD_HEX): cv.string,
    vol.Optional(FIELD_RGB): vol.All(
        cv.ensure_list,
        vol.Length(min=3, max=3),
        [vol.All(vol.Coerce(int), vol.Range(min=0, max=255))],
    ),
    vol.Optional(FIELD_HS): vol.All(
        cv.ensure_list,
        vol.Length(min=2, max=2),
        [vol.Coerce(float)],
    ),
    vol.Optional(FIELD_XY): vol.All(
        cv.ensure_list,
        vol.Length(min=2, max=2),
        [vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0))],
    ),
    vol.Optional(FIELD_KELVIN): vol.All(
        vol.Coerce(int), vol.Range(min=MIN_KELVIN, max=MAX_KELVIN)
    ),
    vol.Optional(FIELD_COLOR_NAME): cv.string,
    vol.Optional(ATTR_BRIGHTNESS): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
}

SET_BRIGHTNESS_SCHEMA = {
    vol.Required(ATTR_BRIGHTNESS): vol.All(vol.Coerce(int), vol.Range(min=0, max=255))
}


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up input color."""
    component = EntityComponent[InputColor](_LOGGER, DOMAIN, hass)

    id_manager = collection.IDManager()

    yaml_collection = collection.YamlCollection(
        logging.getLogger(f"{__name__}.yaml_collection"), id_manager
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, yaml_collection, InputColor
    )

    storage_collection = InputColorStorageCollection(
        Store(hass, STORAGE_VERSION, STORAGE_KEY),
        id_manager,
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, storage_collection, InputColor
    )

    await yaml_collection.async_load(
        [{CONF_ID: id_, **(conf or {})} for id_, conf in config.get(DOMAIN, {}).items()]
    )
    await storage_collection.async_load()

    collection.DictStorageCollectionWebsocket(
        storage_collection, DOMAIN, DOMAIN, STORAGE_FIELDS, STORAGE_FIELDS
    ).async_setup(hass)

    async def reload_service_handler(service_call: ServiceCall) -> None:
        """Reload yaml entities."""
        conf = await component.async_prepare_reload(skip_reset=True)
        await yaml_collection.async_load(
            [{CONF_ID: id_, **(cfg or {})} for id_, cfg in conf.get(DOMAIN, {}).items()]
        )

    homeassistant.helpers.service.async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_RELOAD,
        reload_service_handler,
        schema=RELOAD_SERVICE_SCHEMA,
    )

    strip_keys = {"area_id", "device_id", "entity_id", "floor_id", "label_id"}

    async def set_color(entity: InputColor, call: ServiceCall) -> None:
        """Set an input color from a service call."""
        color_shape = {
            key: value for key, value in call.data.items() if key not in strip_keys
        }
        try:
            await entity.async_set_color(**color_shape)
        except ColorInputError as err:
            raise HomeAssistantError(str(err)) from err

    async def clear_brightness(entity: InputColor, call: ServiceCall) -> None:
        """Clear stored brightness."""
        await entity.async_set_brightness(None)

    component.async_register_entity_service(
        SERVICE_SET_COLOR, SET_COLOR_SCHEMA, set_color
    )
    component.async_register_entity_service(
        SERVICE_SET_BRIGHTNESS, SET_BRIGHTNESS_SCHEMA, "async_set_brightness"
    )
    component.async_register_entity_service(
        SERVICE_CLEAR_BRIGHTNESS, {}, clear_brightness
    )

    return True


class InputColorStorageCollection(collection.DictStorageCollection):
    """Input color storage collection."""

    CREATE_UPDATE_SCHEMA = vol.Schema(vol.All(STORAGE_FIELDS, _cv_input_color))

    @override
    async def _process_create_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate the config is valid."""
        return self.CREATE_UPDATE_SCHEMA(data)  # type: ignore[no-any-return]

    @callback
    @override
    def _get_suggested_id(self, info: dict[str, Any]) -> str:
        """Suggest an ID based on the config."""
        return info[CONF_NAME]  # type: ignore[no-any-return]

    @override
    async def _update_data(
        self, item: dict[str, Any], update_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Return a new updated data object."""
        update_data = self.CREATE_UPDATE_SCHEMA(update_data)
        return {CONF_ID: item[CONF_ID]} | update_data


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
        input_color: Self = cls(config)
        input_color.editable = True
        return input_color

    @classmethod
    @override
    def from_yaml(cls, config: ConfigType) -> Self:
        """Return entity instance initialized from yaml."""
        input_color: Self = cls(config)
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
        return self._config[CONF_ID]  # type: ignore[no-any-return]

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
