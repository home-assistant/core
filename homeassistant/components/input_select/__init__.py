"""Support to select an option from a list."""
from __future__ import annotations

import logging
from typing import Any, cast

import voluptuous as vol

from homeassistant.components.select import SelectEntity
from homeassistant.const import (
    ATTR_EDITABLE,
    ATTR_OPTION,
    CONF_ICON,
    CONF_ID,
    CONF_NAME,
    SERVICE_RELOAD,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import collection
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.integration_platform import (
    async_process_integration_platform_for_component,
)
from homeassistant.helpers.restore_state import RestoreEntity
import homeassistant.helpers.service
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "input_select"

CONF_INITIAL = "initial"
CONF_OPTIONS = "options"

ATTR_OPTIONS = "options"
ATTR_CYCLE = "cycle"

SERVICE_SELECT_OPTION = "select_option"
SERVICE_SELECT_NEXT = "select_next"
SERVICE_SELECT_PREVIOUS = "select_previous"
SERVICE_SELECT_FIRST = "select_first"
SERVICE_SELECT_LAST = "select_last"
SERVICE_SET_OPTIONS = "set_options"
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1
STORAGE_VERSION_MINOR = 2


def _unique(options: Any) -> Any:
    try:
        return vol.Unique()(options)
    except vol.Invalid as exc:
        raise HomeAssistantError("Duplicate options are not allowed") from exc


STORAGE_FIELDS = {
    vol.Required(CONF_NAME): vol.All(str, vol.Length(min=1)),
    vol.Required(CONF_OPTIONS): vol.All(
        cv.ensure_list, vol.Length(min=1), _unique, [cv.string]
    ),
    vol.Optional(CONF_INITIAL): cv.string,
    vol.Optional(CONF_ICON): cv.icon,
}


def _remove_duplicates(options: list[str], name: str | None) -> list[str]:
    """Remove duplicated options."""
    unique_options = list(dict.fromkeys(options))
    # This check was added in 2022.3
    # Reject YAML configured input_select with duplicates from 2022.6
    if len(unique_options) != len(options):
        _LOGGER.warning(
            "Input select '%s' with options %s had duplicated options, the duplicates have been removed",
            name or "<unnamed>",
            options,
        )
    return unique_options


def _cv_input_select(cfg: dict[str, Any]) -> dict[str, Any]:
    """Configure validation helper for input select (voluptuous)."""
    options = cfg[CONF_OPTIONS]
    initial = cfg.get(CONF_INITIAL)
    if initial is not None and initial not in options:
        raise vol.Invalid(
            f"initial state {initial} is not part of the options: {','.join(options)}"
        )
    cfg[CONF_OPTIONS] = _remove_duplicates(options, cfg.get(CONF_NAME))
    return cfg


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: cv.schema_with_slug_keys(
            vol.All(
                {
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Required(CONF_OPTIONS): vol.All(
                        cv.ensure_list, vol.Length(min=1), [cv.string]
                    ),
                    vol.Optional(CONF_INITIAL): cv.string,
                    vol.Optional(CONF_ICON): cv.icon,
                },
                _cv_input_select,
            )
        )
    },
    extra=vol.ALLOW_EXTRA,
)
RELOAD_SERVICE_SCHEMA = vol.Schema({})


class InputSelectStore(Store):
    """Store entity registry data."""

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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up an input select."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    # Process integration platforms right away since
    # we will create entities before firing EVENT_COMPONENT_LOADED
    await async_process_integration_platform_for_component(hass, DOMAIN)

    id_manager = collection.IDManager()

    yaml_collection = collection.YamlCollection(
        logging.getLogger(f"{__name__}.yaml_collection"), id_manager
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, yaml_collection, InputSelect.from_yaml
    )

    storage_collection = InputSelectStorageCollection(
        InputSelectStore(
            hass, STORAGE_VERSION, STORAGE_KEY, minor_version=STORAGE_VERSION_MINOR
        ),
        logging.getLogger(f"{__name__}.storage_collection"),
        id_manager,
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, storage_collection, InputSelect
    )

    await yaml_collection.async_load(
        [{CONF_ID: id_, **cfg} for id_, cfg in config.get(DOMAIN, {}).items()]
    )
    await storage_collection.async_load()

    collection.StorageCollectionWebsocket(
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
        SERVICE_SELECT_OPTION,
        {vol.Required(ATTR_OPTION): cv.string},
        "async_select_option",
    )

    component.async_register_entity_service(
        SERVICE_SELECT_NEXT,
        {vol.Optional(ATTR_CYCLE, default=True): bool},
        "async_next",
    )

    component.async_register_entity_service(
        SERVICE_SELECT_PREVIOUS,
        {vol.Optional(ATTR_CYCLE, default=True): bool},
        "async_previous",
    )

    component.async_register_entity_service(
        SERVICE_SELECT_FIRST,
        {},
        callback(lambda entity, call: entity.async_select_index(0)),
    )

    component.async_register_entity_service(
        SERVICE_SELECT_LAST,
        {},
        callback(lambda entity, call: entity.async_select_index(-1)),
    )

    component.async_register_entity_service(
        SERVICE_SET_OPTIONS,
        {
            vol.Required(ATTR_OPTIONS): vol.All(
                cv.ensure_list, vol.Length(min=1), [cv.string]
            )
        },
        "async_set_options",
    )

    return True


class InputSelectStorageCollection(collection.StorageCollection):
    """Input storage based collection."""

    CREATE_UPDATE_SCHEMA = vol.Schema(vol.All(STORAGE_FIELDS, _cv_input_select))

    async def _process_create_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate the config is valid."""
        return cast(dict[str, Any], self.CREATE_UPDATE_SCHEMA(data))

    @callback
    def _get_suggested_id(self, info: dict[str, Any]) -> str:
        """Suggest an ID based on the config."""
        return cast(str, info[CONF_NAME])

    async def _update_data(
        self, data: dict[str, Any], update_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Return a new updated data object."""
        update_data = self.CREATE_UPDATE_SCHEMA(update_data)
        return {CONF_ID: data[CONF_ID]} | update_data


class InputSelect(SelectEntity, RestoreEntity):
    """Representation of a select input."""

    _attr_should_poll = False
    editable = True

    def __init__(self, config: ConfigType) -> None:
        """Initialize a select input."""
        self._attr_current_option = config.get(CONF_INITIAL)
        self._attr_icon = config.get(CONF_ICON)
        self._attr_name = config.get(CONF_NAME)
        self._attr_options = config[CONF_OPTIONS]
        self._attr_unique_id = config[CONF_ID]

    @classmethod
    def from_yaml(cls, config: ConfigType) -> InputSelect:
        """Return entity instance initialized from yaml storage."""
        input_select = cls(config)
        input_select.entity_id = f"{DOMAIN}.{config[CONF_ID]}"
        input_select.editable = False
        return input_select

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        if self.current_option is not None:
            return

        state = await self.async_get_last_state()
        if not state or state.state not in self.options:
            self._attr_current_option = self.options[0]
        else:
            self._attr_current_option = state.state

    @property
    def extra_state_attributes(self) -> dict[str, bool]:
        """Return the state attributes."""
        return {ATTR_EDITABLE: self.editable}

    async def async_select_option(self, option: str) -> None:
        """Select new option."""
        if option not in self.options:
            _LOGGER.warning(
                "Invalid option: %s (possible options: %s)",
                option,
                ", ".join(self.options),
            )
            return
        self._attr_current_option = option
        self.async_write_ha_state()

    @callback
    def async_select_index(self, idx: int) -> None:
        """Select new option by index."""
        new_index = idx % len(self.options)
        self._attr_current_option = self.options[new_index]
        self.async_write_ha_state()

    @callback
    def async_offset_index(self, offset: int, cycle: bool) -> None:
        """Offset current index."""

        current_index = (
            self.options.index(self.current_option)
            if self.current_option is not None
            else 0
        )

        new_index = current_index + offset
        if cycle:
            new_index = new_index % len(self.options)
        elif new_index < 0:
            new_index = 0
        elif new_index >= len(self.options):
            new_index = len(self.options) - 1

        self._attr_current_option = self.options[new_index]
        self.async_write_ha_state()

    @callback
    def async_next(self, cycle: bool) -> None:
        """Select next option."""
        # If there is no current option, first item is the next
        if self.current_option is None:
            self.async_select_index(0)
            return
        self.async_offset_index(1, cycle)

    @callback
    def async_previous(self, cycle: bool) -> None:
        """Select previous option."""
        # If there is no current option, last item is the previous
        if self.current_option is None:
            self.async_select_index(-1)
            return
        self.async_offset_index(-1, cycle)

    async def async_set_options(self, options: list[str]) -> None:
        """Set options."""
        unique_options = list(dict.fromkeys(options))
        if len(unique_options) != len(options):
            raise HomeAssistantError(f"Duplicated options: {options}")

        self._attr_options = options

        if self.current_option not in self.options:
            _LOGGER.warning(
                "Current option: %s no longer valid (possible options: %s)",
                self.current_option,
                ", ".join(self.options),
            )
            self._attr_current_option = options[0]

        self.async_write_ha_state()

    async def async_update_config(self, config: ConfigType) -> None:
        """Handle when the config is updated."""
        self._attr_icon = config.get(CONF_ICON)
        self._attr_name = config.get(CONF_NAME)
        self._attr_options = config[CONF_OPTIONS]
        self.async_write_ha_state()
