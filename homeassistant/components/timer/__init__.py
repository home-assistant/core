"""Support for Timers."""

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
    CONF_DURATION,
    CONF_RESTORE,
    DATA_TIMER,
    DEFAULT_DURATION,
    DEFAULT_RESTORE,
    DOMAIN,
    SERVICE_CANCEL,
    SERVICE_CHANGE,
    SERVICE_FINISH,
    SERVICE_PAUSE,
    SERVICE_START,
    TimerEntityStateAttribute,
)
from .entity import Timer, _format_timedelta
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

ATTR_REMAINING = "remaining"
ATTR_FINISHES_AT = "finishes_at"
ATTR_RESTORE = "restore"
ATTR_LAST_TRANSITION = "last_transition"


STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

STORAGE_FIELDS: VolDictType = {
    probatio.Required(CONF_NAME): cv.string,
    probatio.Optional(CONF_ICON): cv.icon,
    probatio.Optional(CONF_DURATION, default=DEFAULT_DURATION): cv.time_period,
    probatio.Optional(CONF_RESTORE, default=DEFAULT_RESTORE): cv.boolean,
}

__all__ = [
    "CONF_DURATION",
    "DOMAIN",
    "SERVICE_CANCEL",
    "SERVICE_CHANGE",
    "SERVICE_FINISH",
    "SERVICE_PAUSE",
    "SERVICE_RELOAD",
    "SERVICE_START",
    "STORAGE_FIELDS",
    "Timer",
    "TimerEntityStateAttribute",
    "TimerStorageCollection",
]


def _none_to_empty_dict[_T](value: _T | None) -> _T | dict[Any, Any]:
    if value is None:
        return {}
    return value


CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: cv.schema_with_slug_keys(
            probatio.All(
                _none_to_empty_dict,
                {
                    probatio.Optional(CONF_NAME): cv.string,
                    probatio.Optional(CONF_ICON): cv.icon,
                    probatio.Optional(
                        CONF_DURATION, default=DEFAULT_DURATION
                    ): probatio.All(cv.time_period, _format_timedelta),
                    probatio.Optional(
                        CONF_RESTORE, default=DEFAULT_RESTORE
                    ): cv.boolean,
                },
            )
        )
    },
    extra=probatio.ALLOW_EXTRA,
)


@dataclass(slots=True)
class TimerData:
    """Runtime data for the timer integration."""

    component: EntityComponent[Timer]
    yaml_collection: collection.YamlCollection


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up an input select."""
    component = EntityComponent[Timer](_LOGGER, DOMAIN, hass)
    id_manager = collection.IDManager()

    yaml_collection = collection.YamlCollection(
        logging.getLogger(f"{__name__}.yaml_collection"), id_manager
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, yaml_collection, Timer
    )

    storage_collection = TimerStorageCollection(
        Store(hass, STORAGE_VERSION, STORAGE_KEY),
        id_manager,
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, storage_collection, Timer
    )

    await yaml_collection.async_load(
        [{CONF_ID: id_, **cfg} for id_, cfg in config.get(DOMAIN, {}).items()]
    )
    await storage_collection.async_load()

    collection.DictStorageCollectionWebsocket(
        storage_collection, DOMAIN, DOMAIN, STORAGE_FIELDS, STORAGE_FIELDS
    ).async_setup(hass)

    hass.data[DATA_TIMER] = TimerData(component, yaml_collection)

    async_setup_services(hass)
    return True


class TimerStorageCollection(collection.DictStorageCollection):
    """Timer storage based collection."""

    CREATE_UPDATE_SCHEMA = probatio.Schema(STORAGE_FIELDS)

    @override
    async def _process_create_data(self, data: dict) -> dict:
        """Validate the config is valid."""
        data = self.CREATE_UPDATE_SCHEMA(data)
        # make duration JSON serializeable
        data[CONF_DURATION] = _format_timedelta(data[CONF_DURATION])
        return data

    @callback
    @override
    def _get_suggested_id(self, info: dict) -> str:
        """Suggest an ID based on the config."""
        return info[CONF_NAME]  # type: ignore[no-any-return]

    @override
    async def _update_data(self, item: dict, update_data: dict) -> dict:
        """Return a new updated data object."""
        data = {CONF_ID: item[CONF_ID]} | self.CREATE_UPDATE_SCHEMA(update_data)
        # make duration JSON serializeable
        if CONF_DURATION in update_data:
            data[CONF_DURATION] = _format_timedelta(data[CONF_DURATION])
        return data  # type: ignore[no-any-return]
