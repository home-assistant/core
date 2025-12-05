"""Support to select weekdays for use in automation."""

from __future__ import annotations

import logging
from typing import Any, Self

import voluptuous as vol

from homeassistant.const import (
    ATTR_EDITABLE,
    CONF_ICON,
    CONF_ID,
    CONF_NAME,
    SERVICE_RELOAD,
    WEEKDAYS,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import collection, config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
import homeassistant.helpers.service
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType, VolDictType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "input_weekday"

CONF_WEEKDAYS = "weekdays"

ATTR_WEEKDAYS = "weekdays"
ATTR_WEEKDAY = "weekday"

SERVICE_SET_WEEKDAYS = "set_weekdays"
SERVICE_ADD_WEEKDAY = "add_weekday"
SERVICE_REMOVE_WEEKDAY = "remove_weekday"
SERVICE_TOGGLE_WEEKDAY = "toggle_weekday"
SERVICE_CLEAR = "clear"

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

STORAGE_FIELDS: VolDictType = {
    vol.Required(CONF_NAME): vol.All(str, vol.Length(min=1)),
    vol.Optional(CONF_WEEKDAYS, default=list): vol.All(
        cv.ensure_list, [vol.In(WEEKDAYS)]
    ),
    vol.Optional(CONF_ICON): cv.icon,
}


def _cv_input_weekday(cfg: dict[str, Any]) -> dict[str, Any]:
    """Configure validation helper for input weekday (voluptuous)."""
    if CONF_WEEKDAYS in cfg:
        weekdays = cfg[CONF_WEEKDAYS]
        # Remove duplicates while preserving order
        cfg[CONF_WEEKDAYS] = list(dict.fromkeys(weekdays))
    return cfg


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: cv.schema_with_slug_keys(
            vol.All(
                {
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Optional(CONF_WEEKDAYS): vol.All(
                        cv.ensure_list, [vol.In(WEEKDAYS)]
                    ),
                    vol.Optional(CONF_ICON): cv.icon,
                },
                _cv_input_weekday,
            )
        )
    },
    extra=vol.ALLOW_EXTRA,
)
RELOAD_SERVICE_SCHEMA = vol.Schema({})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up an input weekday."""
    component = EntityComponent[InputWeekday](_LOGGER, DOMAIN, hass)

    id_manager = collection.IDManager()

    yaml_collection = collection.YamlCollection(
        logging.getLogger(f"{__name__}.yaml_collection"), id_manager
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, yaml_collection, InputWeekday
    )

    storage_collection = InputWeekdayStorageCollection(
        Store(hass, STORAGE_VERSION, STORAGE_KEY),
        id_manager,
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, storage_collection, InputWeekday
    )

    await yaml_collection.async_load(
        [{CONF_ID: id_, **cfg} for id_, cfg in config.get(DOMAIN, {}).items()]
    )
    await storage_collection.async_load()

    collection.DictStorageCollectionWebsocket(
        storage_collection, DOMAIN, DOMAIN, STORAGE_FIELDS, STORAGE_FIELDS
    ).async_setup(hass)

    async def reload_service_handler(service_call: ServiceCall) -> None:
        """Reload yaml entities."""
        conf = await component.async_prepare_reload(skip_reset=True)
        if conf is None:
            conf = {DOMAIN: {}}
        await yaml_collection.async_load(
            [{CONF_ID: id_, **cfg} for id_, cfg in conf.get(DOMAIN, {}).items()]
        )

    homeassistant.helpers.service.async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_RELOAD,
        reload_service_handler,
        schema=RELOAD_SERVICE_SCHEMA,
    )

    component.async_register_entity_service(
        SERVICE_SET_WEEKDAYS,
        {vol.Required(ATTR_WEEKDAYS): vol.All(cv.ensure_list, [vol.In(WEEKDAYS)])},
        "async_set_weekdays",
    )

    component.async_register_entity_service(
        SERVICE_ADD_WEEKDAY,
        {vol.Required(ATTR_WEEKDAY): vol.In(WEEKDAYS)},
        "async_add_weekday",
    )

    component.async_register_entity_service(
        SERVICE_REMOVE_WEEKDAY,
        {vol.Required(ATTR_WEEKDAY): vol.In(WEEKDAYS)},
        "async_remove_weekday",
    )

    component.async_register_entity_service(
        SERVICE_TOGGLE_WEEKDAY,
        {vol.Required(ATTR_WEEKDAY): vol.In(WEEKDAYS)},
        "async_toggle_weekday",
    )

    component.async_register_entity_service(
        SERVICE_CLEAR,
        None,
        "async_clear",
    )

    return True


class InputWeekdayStorageCollection(collection.DictStorageCollection):
    """Input weekday storage based collection."""

    CREATE_UPDATE_SCHEMA = vol.Schema(vol.All(STORAGE_FIELDS, _cv_input_weekday))

    async def _process_create_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate the config is valid."""
        return self.CREATE_UPDATE_SCHEMA(data)

    @callback
    def _get_suggested_id(self, info: dict[str, Any]) -> str:
        """Suggest an ID based on the config."""
        return info[CONF_NAME]

    async def _update_data(
        self, item: dict[str, Any], update_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Return a new updated data object."""
        update_data = self.CREATE_UPDATE_SCHEMA(update_data)
        return item | update_data


# pylint: disable-next=hass-enforce-class-module
class InputWeekday(collection.CollectionEntity, RestoreEntity):
    """Representation of a weekday input."""

    _unrecorded_attributes = frozenset({ATTR_EDITABLE})

    _attr_should_poll = False
    editable: bool

    def __init__(self, config: ConfigType) -> None:
        """Initialize a weekday input."""
        self._config = config
        self._attr_weekdays = config.get(CONF_WEEKDAYS, [])
        self._attr_unique_id = config[CONF_ID]

    @classmethod
    def from_storage(cls, config: ConfigType) -> Self:
        """Return entity instance initialized from storage."""
        input_weekday = cls(config)
        input_weekday.editable = True
        return input_weekday

    @classmethod
    def from_yaml(cls, config: ConfigType) -> Self:
        """Return entity instance initialized from yaml."""
        input_weekday = cls(config)
        input_weekday.entity_id = f"{DOMAIN}.{config[CONF_ID]}"
        input_weekday.editable = False
        return input_weekday

    @property
    def name(self) -> str:
        """Return name of the weekday input."""
        return self._config.get(CONF_NAME) or self._config[CONF_ID]

    @property
    def icon(self) -> str | None:
        """Return the icon to be used for this entity."""
        return self._config.get(CONF_ICON)

    @property
    def state(self) -> str:
        """Return the state of the entity."""
        # Return a comma-separated string of selected weekdays
        return ",".join(self._attr_weekdays) if self._attr_weekdays else ""

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the entity."""
        return {
            ATTR_WEEKDAYS: self._attr_weekdays,
            ATTR_EDITABLE: self.editable,
        }

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()

        # Restore previous state if no initial weekdays were provided
        if self._config.get(CONF_WEEKDAYS) is not None:
            return

        state = await self.async_get_last_state()
        if state is not None and ATTR_WEEKDAYS in state.attributes:
            self._attr_weekdays = state.attributes[ATTR_WEEKDAYS]

    async def async_set_weekdays(self, weekdays: list[str]) -> None:
        """Set the selected weekdays."""
        # Remove duplicates while preserving order
        self._attr_weekdays = list(dict.fromkeys(weekdays))
        self.async_write_ha_state()

    async def async_add_weekday(self, weekday: str) -> None:
        """Add a weekday to the selection."""
        if weekday not in self._attr_weekdays:
            self._attr_weekdays.append(weekday)
            self.async_write_ha_state()

    async def async_remove_weekday(self, weekday: str) -> None:
        """Remove a weekday from the selection."""
        if weekday in self._attr_weekdays:
            self._attr_weekdays.remove(weekday)
            self.async_write_ha_state()

    async def async_toggle_weekday(self, weekday: str) -> None:
        """Toggle a weekday in the selection."""
        if weekday in self._attr_weekdays:
            self._attr_weekdays.remove(weekday)
        else:
            self._attr_weekdays.append(weekday)
        self.async_write_ha_state()

    async def async_clear(self) -> None:
        """Clear all selected weekdays."""
        self._attr_weekdays = []
        self.async_write_ha_state()

    async def async_update_config(self, config: ConfigType) -> None:
        """Handle when the config is updated."""
        self._config = config
        self._attr_weekdays = config.get(CONF_WEEKDAYS, [])
        self.async_write_ha_state()
