"""Support to enter a value into a text box."""

from dataclasses import dataclass
import logging
from typing import Any, override

import probatio

from homeassistant.const import (
    CONF_ICON,
    CONF_ID,
    CONF_MODE,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    MAX_LENGTH_STATE_STATE,
    SERVICE_RELOAD,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import collection, config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType, VolDictType

from .const import (
    ATTR_VALUE,
    CONF_INITIAL,
    CONF_MAX,
    CONF_MIN,
    CONF_PATTERN,
    DATA_INPUT_TEXT,
    DOMAIN,
    SERVICE_SET_VALUE,
    InputTextService,
    InputTextServiceArgument,
)
from .entity import InputText
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)


CONF_MIN_VALUE = 0
CONF_MAX_VALUE = 100

MODE_TEXT = "text"
MODE_PASSWORD = "password"


STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

STORAGE_FIELDS: VolDictType = {
    probatio.Required(CONF_NAME): probatio.All(str, probatio.NonEmpty()),
    probatio.Optional(CONF_MIN, default=CONF_MIN_VALUE): probatio.All(
        probatio.Coerce(int), probatio.Range(0, MAX_LENGTH_STATE_STATE)
    ),
    probatio.Optional(CONF_MAX, default=CONF_MAX_VALUE): probatio.All(
        probatio.Coerce(int), probatio.Range(1, MAX_LENGTH_STATE_STATE)
    ),
    probatio.Optional(CONF_INITIAL, ""): cv.string,
    probatio.Optional(CONF_ICON): cv.icon,
    probatio.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    probatio.Optional(CONF_PATTERN): cv.string,
    probatio.Optional(CONF_MODE, default=MODE_TEXT): probatio.In(
        [MODE_TEXT, MODE_PASSWORD]
    ),
}

__all__ = [
    "ATTR_VALUE",
    "DOMAIN",
    "SERVICE_RELOAD",
    "SERVICE_SET_VALUE",
    "STORAGE_FIELDS",
    "InputTextService",
    "InputTextServiceArgument",
]


def _cv_input_text(config: dict[str, Any]) -> dict[str, Any]:
    """Configure validation helper for input box (probatio)."""
    minimum: int = config[CONF_MIN]
    maximum: int = config[CONF_MAX]
    if minimum > maximum:
        raise probatio.Invalid(
            f"Max len ({minimum}) is not greater than min len ({maximum})"
        )
    state: str | None = config.get(CONF_INITIAL)
    if state is not None and (len(state) < minimum or len(state) > maximum):
        raise probatio.Invalid(
            f"Initial value {state} length not in range {minimum}-{maximum}"
        )
    return config


CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: cv.schema_with_slug_keys(
            probatio.All(
                lambda value: value or {},
                {
                    probatio.Optional(CONF_NAME): cv.string,
                    probatio.Optional(CONF_MIN, default=CONF_MIN_VALUE): probatio.All(
                        probatio.Coerce(int), probatio.Range(0, MAX_LENGTH_STATE_STATE)
                    ),
                    probatio.Optional(CONF_MAX, default=CONF_MAX_VALUE): probatio.All(
                        probatio.Coerce(int), probatio.Range(1, MAX_LENGTH_STATE_STATE)
                    ),
                    probatio.Optional(CONF_INITIAL): cv.string,
                    probatio.Optional(CONF_ICON): cv.icon,
                    probatio.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
                    probatio.Optional(CONF_PATTERN): cv.string,
                    probatio.Optional(CONF_MODE, default=MODE_TEXT): probatio.In(
                        [MODE_TEXT, MODE_PASSWORD]
                    ),
                },
                _cv_input_text,
            ),
        )
    },
    extra=probatio.ALLOW_EXTRA,
)


@dataclass(slots=True)
class InputTextData:
    """Runtime data for the input_text integration."""

    component: EntityComponent[InputText]
    yaml_collection: collection.YamlCollection


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up an input text."""
    component = EntityComponent[InputText](_LOGGER, DOMAIN, hass)

    id_manager = collection.IDManager()

    yaml_collection = collection.YamlCollection(
        logging.getLogger(f"{__name__}.yaml_collection"), id_manager
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, yaml_collection, InputText
    )

    storage_collection = InputTextStorageCollection(
        Store(hass, STORAGE_VERSION, STORAGE_KEY),
        id_manager,
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, storage_collection, InputText
    )

    await yaml_collection.async_load(
        [{CONF_ID: id_, **(conf or {})} for id_, conf in config.get(DOMAIN, {}).items()]
    )
    await storage_collection.async_load()

    collection.DictStorageCollectionWebsocket(
        storage_collection, DOMAIN, DOMAIN, STORAGE_FIELDS, STORAGE_FIELDS
    ).async_setup(hass)

    hass.data[DATA_INPUT_TEXT] = InputTextData(component, yaml_collection)

    async_setup_services(hass)
    return True


class InputTextStorageCollection(collection.DictStorageCollection):
    """Input storage based collection."""

    CREATE_UPDATE_SCHEMA = probatio.Schema(probatio.All(STORAGE_FIELDS, _cv_input_text))

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
