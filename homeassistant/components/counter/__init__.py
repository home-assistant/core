"""Component to count within automations."""

import logging
from typing import Any, override

import probatio

from homeassistant.const import (
    CONF_ICON,
    CONF_ID,
    CONF_MAXIMUM,
    CONF_MINIMUM,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import collection, config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType, VolDictType

from .const import (  # noqa: F401
    CONF_INITIAL,
    CONF_RESTORE,
    CONF_STEP,
    DATA_COMPONENT,
    DOMAIN,
    SERVICE_DECREMENT,
    SERVICE_INCREMENT,
    SERVICE_RESET,
    SERVICE_SET_VALUE,
    VALUE,
    CounterEntityStateAttribute,
)
from .entity import Counter
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

ATTR_INITIAL = "initial"
ATTR_STEP = "step"
ATTR_MINIMUM = "minimum"
ATTR_MAXIMUM = "maximum"

DEFAULT_INITIAL = 0
DEFAULT_STEP = 1


STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

STORAGE_FIELDS: VolDictType = {
    probatio.Optional(CONF_ICON): cv.icon,
    probatio.Optional(CONF_INITIAL, default=DEFAULT_INITIAL): probatio.Coerce(int),
    probatio.Required(CONF_NAME): probatio.All(cv.string, probatio.NonEmpty()),
    probatio.Optional(CONF_MAXIMUM, default=None): probatio.Any(
        None, probatio.Coerce(int)
    ),
    probatio.Optional(CONF_MINIMUM, default=None): probatio.Any(
        None, probatio.Coerce(int)
    ),
    probatio.Optional(CONF_RESTORE, default=True): cv.boolean,
    probatio.Optional(CONF_STEP, default=DEFAULT_STEP): cv.positive_int,
}


def _none_to_empty_dict[_T](value: _T | None) -> _T | dict[str, Any]:
    if value is None:
        return {}
    return value


CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: cv.schema_with_slug_keys(
            probatio.All(
                _none_to_empty_dict,
                {
                    probatio.Optional(CONF_ICON): cv.icon,
                    probatio.Optional(
                        CONF_INITIAL, default=DEFAULT_INITIAL
                    ): probatio.Coerce(int),
                    probatio.Optional(CONF_NAME): cv.string,
                    probatio.Optional(CONF_MAXIMUM, default=None): probatio.Any(
                        None, probatio.Coerce(int)
                    ),
                    probatio.Optional(CONF_MINIMUM, default=None): probatio.Any(
                        None, probatio.Coerce(int)
                    ),
                    probatio.Optional(CONF_RESTORE, default=True): cv.boolean,
                    probatio.Optional(CONF_STEP, default=DEFAULT_STEP): cv.positive_int,
                },
            )
        )
    },
    extra=probatio.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the counters."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[Counter](
        _LOGGER, DOMAIN, hass
    )
    id_manager = collection.IDManager()

    yaml_collection = collection.YamlCollection(
        logging.getLogger(f"{__name__}.yaml_collection"), id_manager
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, yaml_collection, Counter
    )

    storage_collection = CounterStorageCollection(
        Store(hass, STORAGE_VERSION, STORAGE_KEY),
        id_manager,
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, storage_collection, Counter
    )

    await yaml_collection.async_load(
        [{CONF_ID: id_, **(conf or {})} for id_, conf in config.get(DOMAIN, {}).items()]
    )
    await storage_collection.async_load()

    collection.DictStorageCollectionWebsocket(
        storage_collection, DOMAIN, DOMAIN, STORAGE_FIELDS, STORAGE_FIELDS
    ).async_setup(hass)

    async_setup_services(hass)
    return True


class CounterStorageCollection(collection.DictStorageCollection):
    """Input storage based collection."""

    CREATE_UPDATE_SCHEMA = probatio.Schema(STORAGE_FIELDS)

    @override
    async def _process_create_data(self, data: dict) -> dict:
        """Validate the config is valid."""
        return self.CREATE_UPDATE_SCHEMA(data)  # type: ignore[no-any-return]

    @callback
    @override
    def _get_suggested_id(self, info: dict) -> str:
        """Suggest an ID based on the config."""
        return info[CONF_NAME]  # type: ignore[no-any-return]

    @override
    async def _update_data(self, item: dict, update_data: dict) -> dict:
        """Return a new updated data object."""
        update_data = self.CREATE_UPDATE_SCHEMA(update_data)
        return {CONF_ID: item[CONF_ID]} | update_data
