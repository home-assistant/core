"""Support to keep track of user controlled booleans for within automation."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.const import (
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
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import collection
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
import homeassistant.helpers.service
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass

DOMAIN = "input_boolean"

_LOGGER = logging.getLogger(__name__)

CONF_INITIAL = "initial"

CREATE_FIELDS = {
    vol.Required(CONF_NAME): vol.All(str, vol.Length(min=1)),
    vol.Optional(CONF_INITIAL): cv.boolean,
    vol.Optional(CONF_ICON): cv.icon,
}

UPDATE_FIELDS = {
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_INITIAL): cv.boolean,
    vol.Optional(CONF_ICON): cv.icon,
}

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: cv.schema_with_slug_keys(vol.Any(UPDATE_FIELDS, None))},
    extra=vol.ALLOW_EXTRA,
)

RELOAD_SERVICE_SCHEMA = vol.Schema({})
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1


class InputBooleanStorageCollection(collection.StorageCollection):
    """Input boolean collection stored in storage."""

    CREATE_SCHEMA = vol.Schema(CREATE_FIELDS)
    UPDATE_SCHEMA = vol.Schema(UPDATE_FIELDS)

    async def _process_create_data(self, data: dict) -> dict:
        """Validate the config is valid."""
        return self.CREATE_SCHEMA(data)

    @callback
    def _get_suggested_id(self, info: dict) -> str:
        """Suggest an ID based on the config."""
        return info[CONF_NAME]

    async def _update_data(self, data: dict, update_data: dict) -> dict:
        """Return a new updated data object."""
        update_data = self.UPDATE_SCHEMA(update_data)
        return {**data, **update_data}


@bind_hass
def is_on(hass, entity_id):
    """Test if input_boolean is True."""
    return hass.states.is_state(entity_id, STATE_ON)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up an input boolean."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    id_manager = collection.IDManager()

    yaml_collection = collection.YamlCollection(
        logging.getLogger(f"{__name__}.yaml_collection"), id_manager
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, yaml_collection, InputBoolean.from_yaml
    )

    storage_collection = InputBooleanStorageCollection(
        Store(hass, STORAGE_VERSION, STORAGE_KEY),
        logging.getLogger(f"{__name__}.storage_collection"),
        id_manager,
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, storage_collection, InputBoolean
    )

    await yaml_collection.async_load(
        [{CONF_ID: id_, **(conf or {})} for id_, conf in config.get(DOMAIN, {}).items()]
    )
    await storage_collection.async_load()

    collection.StorageCollectionWebsocket(
        storage_collection, DOMAIN, DOMAIN, CREATE_FIELDS, UPDATE_FIELDS
    ).async_setup(hass)

    async def reload_service_handler(service_call: ServiceCall) -> None:
        """Remove all input booleans and load new ones from config."""
        conf = await component.async_prepare_reload(skip_reset=True)
        if conf is None:
            return
        await yaml_collection.async_load(
            [
                {CONF_ID: id_, **(conf or {})}
                for id_, conf in conf.get(DOMAIN, {}).items()
            ]
        )

    homeassistant.helpers.service.async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_RELOAD,
        reload_service_handler,
        schema=RELOAD_SERVICE_SCHEMA,
    )

    component.async_register_entity_service(SERVICE_TURN_ON, {}, "async_turn_on")

    component.async_register_entity_service(SERVICE_TURN_OFF, {}, "async_turn_off")

    component.async_register_entity_service(SERVICE_TOGGLE, {}, "async_toggle")

    return True


class InputBoolean(ToggleEntity, RestoreEntity):
    """Representation of a boolean input."""

    def __init__(self, config: dict | None):
        """Initialize a boolean input."""
        self._config = config
        self.editable = True
        self._state = config.get(CONF_INITIAL)

    @classmethod
    def from_yaml(cls, config: dict) -> InputBoolean:
        """Return entity instance initialized from yaml storage."""
        input_bool = cls(config)
        input_bool.entity_id = f"{DOMAIN}.{config[CONF_ID]}"
        input_bool.editable = False
        return input_bool

    @property
    def should_poll(self):
        """If entity should be polled."""
        return False

    @property
    def name(self):
        """Return name of the boolean input."""
        return self._config.get(CONF_NAME)

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the entity."""
        return {ATTR_EDITABLE: self.editable}

    @property
    def icon(self):
        """Return the icon to be used for this entity."""
        return self._config.get(CONF_ICON)

    @property
    def is_on(self):
        """Return true if entity is on."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique ID for the person."""
        return self._config[CONF_ID]

    async def async_added_to_hass(self):
        """Call when entity about to be added to hass."""
        # If not None, we got an initial value.
        await super().async_added_to_hass()
        if self._state is not None:
            return

        state = await self.async_get_last_state()
        self._state = state and state.state == STATE_ON

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        self._state = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        self._state = False
        self.async_write_ha_state()

    async def async_update_config(self, config: dict) -> None:
        """Handle when the config is updated."""
        self._config = config
        self.async_write_ha_state()
