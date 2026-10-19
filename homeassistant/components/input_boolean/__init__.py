"""Support to keep track of user controlled booleans for within automation."""

from dataclasses import dataclass
import logging
from typing import override

import probatio

from homeassistant.const import (  # noqa: F401
    ATTR_EDITABLE,
    CONF_ICON,
    CONF_ID,
    CONF_NAME,
    SERVICE_RELOAD,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import collection, config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType, VolDictType

from .const import CONF_INITIAL, DATA_INPUT_BOOLEAN, DOMAIN
from .entity import InputBoolean
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

STORAGE_FIELDS: VolDictType = {
    probatio.Required(CONF_NAME): probatio.All(str, probatio.NonEmpty()),
    probatio.Optional(CONF_INITIAL): cv.boolean,
    probatio.Optional(CONF_ICON): cv.icon,
}

CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: cv.schema_with_slug_keys(
            probatio.Any(
                {
                    probatio.Optional(CONF_NAME): cv.string,
                    probatio.Optional(CONF_INITIAL): cv.boolean,
                    probatio.Optional(CONF_ICON): cv.icon,
                },
                None,
            )
        )
    },
    extra=probatio.ALLOW_EXTRA,
)

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1


class InputBooleanStorageCollection(collection.DictStorageCollection):
    """Input boolean collection stored in storage."""

    CREATE_UPDATE_SCHEMA = probatio.Schema(STORAGE_FIELDS)

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


def is_on(hass: HomeAssistant, entity_id: str) -> bool:
    """Test if input_boolean is True."""
    return hass.states.is_state(entity_id, STATE_ON)


@dataclass(slots=True)
class InputBooleanData:
    """Runtime data for the input_boolean integration."""

    component: EntityComponent[InputBoolean]
    yaml_collection: collection.YamlCollection


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up an input boolean."""
    component = EntityComponent[InputBoolean](_LOGGER, DOMAIN, hass)

    id_manager = collection.IDManager()

    yaml_collection = collection.YamlCollection(
        logging.getLogger(f"{__name__}.yaml_collection"), id_manager
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, yaml_collection, InputBoolean
    )

    storage_collection = InputBooleanStorageCollection(
        Store(hass, STORAGE_VERSION, STORAGE_KEY),
        id_manager,
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, storage_collection, InputBoolean
    )

    await yaml_collection.async_load(
        [{CONF_ID: id_, **(conf or {})} for id_, conf in config.get(DOMAIN, {}).items()]
    )
    await storage_collection.async_load()

    collection.DictStorageCollectionWebsocket(
        storage_collection, DOMAIN, DOMAIN, STORAGE_FIELDS, STORAGE_FIELDS
    ).async_setup(hass)

    hass.data[DATA_INPUT_BOOLEAN] = InputBooleanData(component, yaml_collection)

    async_setup_services(hass)

    return True
