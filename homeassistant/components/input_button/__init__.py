"""Support to keep track of user controlled buttons which can be used in automations."""

from dataclasses import dataclass
import logging
from typing import cast, override

import probatio

from homeassistant.components.button import SERVICE_PRESS
from homeassistant.const import CONF_ICON, CONF_ID, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import collection, config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType, VolDictType

from .const import (
    DATA_INPUT_BUTTON,
    DOMAIN,
    InputButtonEntityStateAttribute,
    InputButtonService,
)
from .entity import InputButton
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

STORAGE_FIELDS: VolDictType = {
    probatio.Required(CONF_NAME): probatio.All(str, probatio.NonEmpty()),
    probatio.Optional(CONF_ICON): cv.icon,
}

CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: cv.schema_with_slug_keys(
            probatio.Any(
                {
                    probatio.Optional(CONF_NAME): cv.string,
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

__all__ = [
    "DOMAIN",
    "SERVICE_PRESS",
    "STORAGE_FIELDS",
    "InputButtonEntityStateAttribute",
    "InputButtonService",
]


class InputButtonStorageCollection(collection.DictStorageCollection):
    """Input button collection stored in storage."""

    CREATE_UPDATE_SCHEMA = probatio.Schema(STORAGE_FIELDS)

    @override
    async def _process_create_data(self, data: dict) -> dict[str, str]:
        """Validate the config is valid."""
        return self.CREATE_UPDATE_SCHEMA(data)  # type: ignore[no-any-return]

    @callback
    @override
    def _get_suggested_id(self, info: dict) -> str:
        """Suggest an ID based on the config."""
        return cast(str, info[CONF_NAME])

    @override
    async def _update_data(self, item: dict, update_data: dict) -> dict:
        """Return a new updated data object."""
        update_data = self.CREATE_UPDATE_SCHEMA(update_data)
        return {CONF_ID: item[CONF_ID]} | update_data


@dataclass(slots=True)
class InputButtonData:
    """Runtime data for the input_button integration."""

    component: EntityComponent[InputButton]
    yaml_collection: collection.YamlCollection


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up an input button."""
    component = EntityComponent[InputButton](_LOGGER, DOMAIN, hass)

    id_manager = collection.IDManager()

    yaml_collection = collection.YamlCollection(
        logging.getLogger(f"{__name__}.yaml_collection"), id_manager
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, yaml_collection, InputButton
    )

    storage_collection = InputButtonStorageCollection(
        Store(hass, STORAGE_VERSION, STORAGE_KEY),
        id_manager,
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, storage_collection, InputButton
    )

    await yaml_collection.async_load(
        [{CONF_ID: id_, **(conf or {})} for id_, conf in config.get(DOMAIN, {}).items()]
    )
    await storage_collection.async_load()

    collection.DictStorageCollectionWebsocket(
        storage_collection, DOMAIN, DOMAIN, STORAGE_FIELDS, STORAGE_FIELDS
    ).async_setup(hass)

    hass.data[DATA_INPUT_BUTTON] = InputButtonData(component, yaml_collection)

    async_setup_services(hass)
    return True
