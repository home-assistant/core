"""Support for schedules in Home Assistant."""

from dataclasses import dataclass
from typing import override

import probatio

from homeassistant.const import (  # noqa: F401
    ATTR_EDITABLE,
    CONF_ICON,
    CONF_ID,
    CONF_NAME,
    SERVICE_RELOAD,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.collection import (
    DictStorageCollection,
    DictStorageCollectionWebsocket,
    IDManager,
    SerializedStorageCollection,
    YamlCollection,
    sync_entity_lifecycle,
)
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .const import (  # noqa: F401
    ATTR_NEXT_EVENT,
    CONF_ALL_DAYS,
    CONF_DATA,
    CONF_FROM,
    CONF_TO,
    DATA_SCHEDULE,
    DOMAIN,
    LOGGER,
    SERVICE_GET,
    WEEKDAY_TO_CONF,
    ScheduleEntityCapabilityAttribute,
    ScheduleEntityStateAttribute,
)
from .entity import Schedule
from .schema import (
    BASE_SCHEMA,
    SCHEDULE_SCHEMA,
    STORAGE_SCHEDULE_SCHEMA,
    STORAGE_SCHEMA,
)
from .services import async_setup_services

STORAGE_VERSION = 1
STORAGE_VERSION_MINOR = 1


# Validate YAML config
CONFIG_SCHEMA = probatio.Schema(
    {DOMAIN: cv.schema_with_slug_keys(probatio.All(BASE_SCHEMA | SCHEDULE_SCHEMA))},
    extra=probatio.ALLOW_EXTRA,
)


@dataclass(slots=True)
class ScheduleData:
    """Runtime data for the schedule integration."""

    component: EntityComponent[Schedule]
    yaml_collection: YamlCollection


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up a schedule."""
    component = EntityComponent[Schedule](LOGGER, DOMAIN, hass)

    id_manager = IDManager()

    yaml_collection = YamlCollection(LOGGER, id_manager)
    sync_entity_lifecycle(hass, DOMAIN, DOMAIN, component, yaml_collection, Schedule)

    storage_collection = ScheduleStorageCollection(
        Store(
            hass,
            key=DOMAIN,
            version=STORAGE_VERSION,
            minor_version=STORAGE_VERSION_MINOR,
        ),
        id_manager,
    )
    sync_entity_lifecycle(hass, DOMAIN, DOMAIN, component, storage_collection, Schedule)

    await yaml_collection.async_load(
        [{CONF_ID: id_, **cfg} for id_, cfg in config.get(DOMAIN, {}).items()]
    )
    await storage_collection.async_load()

    DictStorageCollectionWebsocket(
        storage_collection,
        DOMAIN,
        DOMAIN,
        BASE_SCHEMA | STORAGE_SCHEDULE_SCHEMA,
        BASE_SCHEMA | STORAGE_SCHEDULE_SCHEMA,
    ).async_setup(hass)

    hass.data[DATA_SCHEDULE] = ScheduleData(component, yaml_collection)

    async_setup_services(hass)

    await component.async_setup(config)

    return True


class ScheduleStorageCollection(DictStorageCollection):
    """Schedules stored in storage."""

    SCHEMA = probatio.Schema(BASE_SCHEMA | STORAGE_SCHEDULE_SCHEMA)

    @override
    async def _process_create_data(self, data: dict) -> dict:
        """Validate the config is valid."""
        self.SCHEMA(data)
        return data

    @callback
    @override
    def _get_suggested_id(self, info: dict) -> str:
        """Suggest an ID based on the config."""
        name: str = info[CONF_NAME]
        return name

    @override
    async def _update_data(self, item: dict, update_data: dict) -> dict:
        """Return a new updated data object."""
        self.SCHEMA(update_data)
        return {CONF_ID: item[CONF_ID]} | update_data

    @override
    async def _async_load_data(self) -> SerializedStorageCollection | None:
        """Load the data."""
        if data := await super()._async_load_data():
            data["items"] = [STORAGE_SCHEMA(item) for item in data["items"]]
        return data
