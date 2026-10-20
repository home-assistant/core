"""Support to select a date and/or a time."""

from dataclasses import dataclass
import logging
from typing import Any, override

import probatio

from homeassistant.const import CONF_ICON, CONF_ID, CONF_NAME, SERVICE_RELOAD
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import collection, config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType, VolDictType

from .const import (
    CONF_HAS_DATE,
    CONF_HAS_TIME,
    CONF_INITIAL,
    DATA_INPUT_DATETIME,
    DOMAIN,
)
from .entity import InputDatetime, parse_initial_datetime
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)


STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

STORAGE_FIELDS: VolDictType = {
    probatio.Required(CONF_NAME): probatio.All(str, probatio.NonEmpty()),
    probatio.Optional(CONF_HAS_DATE, default=False): cv.boolean,
    probatio.Optional(CONF_HAS_TIME, default=False): cv.boolean,
    probatio.Optional(CONF_ICON): cv.icon,
    probatio.Optional(CONF_INITIAL): cv.string,
}

__all__ = [
    "CONF_HAS_DATE",
    "CONF_HAS_TIME",
    "CONF_INITIAL",
    "DOMAIN",
    "SERVICE_RELOAD",
    "STORAGE_FIELDS",
    "InputDatetime",
    "valid_initial",
]


def has_date_or_time(conf):
    """Check at least date or time is true."""
    if conf[CONF_HAS_DATE] or conf[CONF_HAS_TIME]:
        return conf

    raise probatio.Invalid("Entity needs at least a date or a time")


def valid_initial(conf: dict[str, Any]) -> dict[str, Any]:
    """Check the initial value is valid."""
    if not (conf.get(CONF_INITIAL)):
        return conf

    # Ensure we can parse the initial value, raise probatio.Invalid on failure
    parse_initial_datetime(conf)
    return conf


CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: cv.schema_with_slug_keys(
            probatio.All(
                {
                    probatio.Optional(CONF_NAME): cv.string,
                    probatio.Optional(CONF_HAS_DATE, default=False): cv.boolean,
                    probatio.Optional(CONF_HAS_TIME, default=False): cv.boolean,
                    probatio.Optional(CONF_ICON): cv.icon,
                    probatio.Optional(CONF_INITIAL): cv.string,
                },
                has_date_or_time,
                valid_initial,
            )
        )
    },
    extra=probatio.ALLOW_EXTRA,
)


@dataclass(slots=True)
class InputDatetimeData:
    """Runtime data for the input_datetime integration."""

    component: EntityComponent[InputDatetime]
    yaml_collection: collection.YamlCollection


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up an input datetime."""
    component = EntityComponent[InputDatetime](_LOGGER, DOMAIN, hass)

    id_manager = collection.IDManager()

    yaml_collection = collection.YamlCollection(
        logging.getLogger(f"{__name__}.yaml_collection"), id_manager
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, yaml_collection, InputDatetime
    )

    storage_collection = DateTimeStorageCollection(
        Store(hass, STORAGE_VERSION, STORAGE_KEY),
        id_manager,
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, storage_collection, InputDatetime
    )

    await yaml_collection.async_load(
        [{CONF_ID: id_, **cfg} for id_, cfg in config.get(DOMAIN, {}).items()]
    )
    await storage_collection.async_load()

    collection.DictStorageCollectionWebsocket(
        storage_collection, DOMAIN, DOMAIN, STORAGE_FIELDS, STORAGE_FIELDS
    ).async_setup(hass)

    hass.data[DATA_INPUT_DATETIME] = InputDatetimeData(component, yaml_collection)

    async_setup_services(hass)
    return True


class DateTimeStorageCollection(collection.DictStorageCollection):
    """Input storage based collection."""

    CREATE_UPDATE_SCHEMA = probatio.Schema(
        probatio.All(STORAGE_FIELDS, has_date_or_time)
    )

    @override
    async def _process_create_data(self, data: dict) -> dict:
        """Validate the config is valid."""
        return self.CREATE_UPDATE_SCHEMA(data)

    @callback
    @override
    def _get_suggested_id(self, info: dict) -> str:
        """Suggest an ID based on the config."""
        return info[CONF_NAME]

    @override
    async def _update_data(self, item: dict, update_data: dict) -> dict:
        """Return a new updated data object."""
        update_data = self.CREATE_UPDATE_SCHEMA(update_data)
        return {CONF_ID: item[CONF_ID]} | update_data
