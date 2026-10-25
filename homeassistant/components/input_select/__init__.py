"""Support to select an option from a list."""

from dataclasses import dataclass
import logging
from typing import Any, cast, override

import probatio

from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    SERVICE_SELECT_FIRST,
    SERVICE_SELECT_LAST,
    SERVICE_SELECT_NEXT,
    SERVICE_SELECT_OPTION,
    SERVICE_SELECT_PREVIOUS,
)
from homeassistant.const import (
    CONF_ICON,
    CONF_ID,
    CONF_NAME,
    CONF_OPTIONS,
    SERVICE_RELOAD,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import collection, config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType, VolDictType

from .const import (
    CONF_INITIAL,
    DATA_INPUT_SELECT,
    DOMAIN,
    SERVICE_SET_OPTIONS,
    InputSelectService,
    InputSelectServiceArgument,
)
from .entity import InputSelect
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1
STORAGE_VERSION_MINOR = 2

__all__ = [
    "ATTR_OPTION",
    "ATTR_OPTIONS",
    "DOMAIN",
    "SERVICE_RELOAD",
    "SERVICE_SELECT_FIRST",
    "SERVICE_SELECT_LAST",
    "SERVICE_SELECT_NEXT",
    "SERVICE_SELECT_OPTION",
    "SERVICE_SELECT_PREVIOUS",
    "SERVICE_SET_OPTIONS",
    "STORAGE_FIELDS",
    "InputSelect",
    "InputSelectService",
    "InputSelectServiceArgument",
]


def _unique(options: Any) -> Any:
    try:
        return probatio.Unique()(options)
    except probatio.Invalid as exc:
        raise HomeAssistantError("Duplicate options are not allowed") from exc


STORAGE_FIELDS: VolDictType = {
    probatio.Required(CONF_NAME): probatio.All(str, probatio.NonEmpty()),
    probatio.Required(CONF_OPTIONS): probatio.All(
        probatio.EnsureList(), probatio.NonEmpty(), _unique, [cv.string]
    ),
    probatio.Optional(CONF_INITIAL): cv.string,
    probatio.Optional(CONF_ICON): cv.icon,
}


def _remove_duplicates(options: list[str], name: str | None) -> list[str]:
    """Remove duplicated options."""
    unique_options = list(dict.fromkeys(options))
    # This check was added in 2022.3
    # Reject YAML configured input_select with duplicates from 2022.6
    if len(unique_options) != len(options):
        _LOGGER.warning(
            (
                "Input select '%s' with options %s had duplicated options, the"
                " duplicates have been removed"
            ),
            name or "<unnamed>",
            options,
        )
    return unique_options


def _cv_input_select(cfg: dict[str, Any]) -> dict[str, Any]:
    """Configure validation helper for input select (probatio)."""
    options = cfg[CONF_OPTIONS]
    initial = cfg.get(CONF_INITIAL)
    if initial is not None and initial not in options:
        raise probatio.Invalid(
            f"initial state {initial} is not part of the options: {','.join(options)}"
        )
    cfg[CONF_OPTIONS] = _remove_duplicates(options, cfg.get(CONF_NAME))
    return cfg


CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: cv.schema_with_slug_keys(
            probatio.All(
                {
                    probatio.Optional(CONF_NAME): cv.string,
                    probatio.Required(CONF_OPTIONS): probatio.All(
                        probatio.EnsureList(), probatio.NonEmpty(), [cv.string]
                    ),
                    probatio.Optional(CONF_INITIAL): cv.string,
                    probatio.Optional(CONF_ICON): cv.icon,
                },
                _cv_input_select,
            )
        )
    },
    extra=probatio.ALLOW_EXTRA,
)


class InputSelectStore(Store):
    """Store entity registry data."""

    @override
    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Migrate to the new version."""
        if old_major_version == 1:
            if old_minor_version < 2:
                for item in old_data["items"]:
                    options = item[ATTR_OPTIONS]
                    item[ATTR_OPTIONS] = _remove_duplicates(
                        options, item.get(CONF_NAME)
                    )
        return old_data


@dataclass(slots=True)
class InputSelectData:
    """Runtime data for the input_select integration."""

    component: EntityComponent[InputSelect]
    yaml_collection: collection.YamlCollection


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up an input select."""
    component = EntityComponent[InputSelect](_LOGGER, DOMAIN, hass)

    id_manager = collection.IDManager()

    yaml_collection = collection.YamlCollection(
        logging.getLogger(f"{__name__}.yaml_collection"), id_manager
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, yaml_collection, InputSelect
    )

    storage_collection = InputSelectStorageCollection(
        InputSelectStore(
            hass, STORAGE_VERSION, STORAGE_KEY, minor_version=STORAGE_VERSION_MINOR
        ),
        id_manager,
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, storage_collection, InputSelect
    )

    await yaml_collection.async_load(
        [{CONF_ID: id_, **cfg} for id_, cfg in config.get(DOMAIN, {}).items()]
    )
    await storage_collection.async_load()

    collection.DictStorageCollectionWebsocket(
        storage_collection, DOMAIN, DOMAIN, STORAGE_FIELDS, STORAGE_FIELDS
    ).async_setup(hass)

    hass.data[DATA_INPUT_SELECT] = InputSelectData(component, yaml_collection)

    async_setup_services(hass)
    return True


class InputSelectStorageCollection(collection.DictStorageCollection):
    """Input storage based collection."""

    CREATE_UPDATE_SCHEMA = probatio.Schema(
        probatio.All(STORAGE_FIELDS, _cv_input_select)
    )

    @override
    async def _process_create_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate the config is valid."""
        return cast(dict[str, Any], self.CREATE_UPDATE_SCHEMA(data))

    @callback
    @override
    def _get_suggested_id(self, info: dict[str, Any]) -> str:
        """Suggest an ID based on the config."""
        return cast(str, info[CONF_NAME])

    @override
    async def _update_data(
        self, item: dict[str, Any], update_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Return a new updated data object."""
        update_data = self.CREATE_UPDATE_SCHEMA(update_data)
        return {CONF_ID: item[CONF_ID]} | update_data
