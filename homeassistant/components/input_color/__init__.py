"""Support to store reusable color values."""

import logging
from typing import Any, override

import voluptuous as vol

from homeassistant.const import CONF_ICON, CONF_ID, CONF_NAME, SERVICE_RELOAD
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import collection, config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
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
    ColorInputError,
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

SET_COLOR_SCHEMA: VolDictType = {
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

SET_BRIGHTNESS_SCHEMA: VolDictType = {
    vol.Required(ATTR_BRIGHTNESS): vol.All(vol.Coerce(int), vol.Range(min=0, max=255))
}

from .entity import InputColor  # noqa: E402


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
        return self.CREATE_UPDATE_SCHEMA(data)

    @callback
    @override
    def _get_suggested_id(self, info: dict[str, Any]) -> str:
        """Suggest an ID based on the config."""
        return info[CONF_NAME]

    @override
    async def _update_data(
        self, item: dict[str, Any], update_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Return a new updated data object."""
        update_data = self.CREATE_UPDATE_SCHEMA(update_data)
        return {CONF_ID: item[CONF_ID]} | update_data
