"""Support to select an option from a list."""
import logging
import typing

import voluptuous as vol

from homeassistant.const import (
    ATTR_EDITABLE,
    CONF_ICON,
    CONF_ID,
    CONF_NAME,
    SERVICE_RELOAD,
)
from homeassistant.core import callback
from homeassistant.helpers import collection
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
import homeassistant.helpers.service
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType, HomeAssistantType, ServiceCallType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "input_select"
ENTITY_ID_FORMAT = DOMAIN + ".{}"

CONF_INITIAL = "initial"
CONF_OPTIONS = "options"

ATTR_OPTION = "option"
ATTR_OPTIONS = "options"

SERVICE_SELECT_OPTION = "select_option"
SERVICE_SELECT_NEXT = "select_next"
SERVICE_SELECT_PREVIOUS = "select_previous"
SERVICE_SET_OPTIONS = "set_options"
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

CREATE_FIELDS = {
    vol.Required(CONF_NAME): vol.All(str, vol.Length(min=1)),
    vol.Required(CONF_OPTIONS): vol.All(cv.ensure_list, vol.Length(min=1), [cv.string]),
    vol.Optional(CONF_INITIAL): cv.string,
    vol.Optional(CONF_ICON): cv.icon,
}
UPDATE_FIELDS = {
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_OPTIONS): vol.All(cv.ensure_list, vol.Length(min=1), [cv.string]),
    vol.Optional(CONF_INITIAL): cv.string,
    vol.Optional(CONF_ICON): cv.icon,
}


def _cv_input_select(cfg):
    """Configure validation helper for input select (voluptuous)."""
    options = cfg[CONF_OPTIONS]
    initial = cfg.get(CONF_INITIAL)
    if initial is not None and initial not in options:
        raise vol.Invalid(
            'initial state "{}" is not part of the options: {}'.format(
                initial, ",".join(options)
            )
        )
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


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up an input select."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    id_manager = collection.IDManager()

    yaml_collection = collection.YamlCollection(
        logging.getLogger(f"{__name__}.yaml_collection"), id_manager
    )
    collection.attach_entity_component_collection(
        component, yaml_collection, InputSelect.from_yaml
    )

    storage_collection = InputSelectStorageCollection(
        Store(hass, STORAGE_VERSION, STORAGE_KEY),
        logging.getLogger(f"{__name__}.storage_collection"),
        id_manager,
    )
    collection.attach_entity_component_collection(
        component, storage_collection, InputSelect
    )

    await yaml_collection.async_load(
        [{CONF_ID: id_, **cfg} for id_, cfg in config.get(DOMAIN, {}).items()]
    )
    await storage_collection.async_load()

    collection.StorageCollectionWebsocket(
        storage_collection, DOMAIN, DOMAIN, CREATE_FIELDS, UPDATE_FIELDS
    ).async_setup(hass)

    collection.attach_entity_registry_cleaner(hass, DOMAIN, DOMAIN, yaml_collection)
    collection.attach_entity_registry_cleaner(hass, DOMAIN, DOMAIN, storage_collection)

    async def reload_service_handler(service_call: ServiceCallType) -> None:
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
        {},
        callback(lambda entity, call: entity.async_offset_index(1)),
    )

    component.async_register_entity_service(
        SERVICE_SELECT_PREVIOUS,
        {},
        callback(lambda entity, call: entity.async_offset_index(-1)),
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

    CREATE_SCHEMA = vol.Schema(vol.All(CREATE_FIELDS, _cv_input_select))
    UPDATE_SCHEMA = vol.Schema(UPDATE_FIELDS)

    async def _process_create_data(self, data: typing.Dict) -> typing.Dict:
        """Validate the config is valid."""
        return self.CREATE_SCHEMA(data)

    @callback
    def _get_suggested_id(self, info: typing.Dict) -> str:
        """Suggest an ID based on the config."""
        return info[CONF_NAME]

    async def _update_data(self, data: dict, update_data: typing.Dict) -> typing.Dict:
        """Return a new updated data object."""
        update_data = self.UPDATE_SCHEMA(update_data)
        return _cv_input_select({**data, **update_data})


class InputSelect(RestoreEntity):
    """Representation of a select input."""

    def __init__(self, config: typing.Dict):
        """Initialize a select input."""
        self._config = config
        self.editable = True
        self._current_option = config.get(CONF_INITIAL)

    @classmethod
    def from_yaml(cls, config: typing.Dict) -> "InputSelect":
        """Return entity instance initialized from yaml storage."""
        input_select = cls(config)
        input_select.entity_id = ENTITY_ID_FORMAT.format(config[CONF_ID])
        input_select.editable = False
        return input_select

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        if self._current_option is not None:
            return

        state = await self.async_get_last_state()
        if not state or state.state not in self._options:
            self._current_option = self._options[0]
        else:
            self._current_option = state.state

    @property
    def should_poll(self):
        """If entity should be polled."""
        return False

    @property
    def name(self):
        """Return the name of the select input."""
        return self._config.get(CONF_NAME)

    @property
    def icon(self):
        """Return the icon to be used for this entity."""
        return self._config.get(CONF_ICON)

    @property
    def _options(self) -> typing.List[str]:
        """Return a list of selection options."""
        return self._config[CONF_OPTIONS]

    @property
    def state(self):
        """Return the state of the component."""
        return self._current_option

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return {ATTR_OPTIONS: self._config[ATTR_OPTIONS], ATTR_EDITABLE: self.editable}

    @property
    def unique_id(self) -> typing.Optional[str]:
        """Return unique id for the entity."""
        return self._config[CONF_ID]

    @callback
    def async_select_option(self, option):
        """Select new option."""
        if option not in self._options:
            _LOGGER.warning(
                "Invalid option: %s (possible options: %s)",
                option,
                ", ".join(self._options),
            )
            return
        self._current_option = option
        self.async_write_ha_state()

    @callback
    def async_offset_index(self, offset):
        """Offset current index."""
        current_index = self._options.index(self._current_option)
        new_index = (current_index + offset) % len(self._options)
        self._current_option = self._options[new_index]
        self.async_write_ha_state()

    @callback
    def async_set_options(self, options):
        """Set options."""
        self._current_option = options[0]
        self._config[CONF_OPTIONS] = options
        self.async_write_ha_state()

    async def async_update_config(self, config: typing.Dict) -> None:
        """Handle when the config is updated."""
        self._config = config
        self.async_write_ha_state()
