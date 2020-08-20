"""The Variables integration."""
import logging
from typing import Union

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv, entity_registry
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)

DOMAIN = "variables"

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1
STORAGE_SAVE_DELAY = 10

DATA_STORAGE = "storage"

TOPIC_VARIABLE_SET = "variables_set_{0}"

UNIQUE_ID_TEMPLATE = "variables_{0}"

CONF_KEY = "key"
CONF_VALUE = "value"

REMOVE_VARIABLE_SCHEMA = vol.Schema({vol.Required(CONF_KEY): cv.string})
SET_VARIABLE_SCHEMA = vol.Schema(
    {vol.Required(CONF_KEY): cv.string, vol.Required(CONF_VALUE): cv.string}
)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Variables component."""
    variable_manager = VariableManager(hass)
    await variable_manager.async_init()

    entity_component = EntityComponent(_LOGGER, DOMAIN, hass)

    async def async_remove_variable(call: ServiceCall):
        """Remove a variable."""
        key = call.data[CONF_KEY]

        value = variable_manager.async_get(key)
        if not value:
            _LOGGER.warning("Can't delete variable that doesn't exist: %s", key)
            return

        _LOGGER.debug("Removing variable: %s", key)

        variable_manager.async_remove(key)

        ent_reg = await entity_registry.async_get_registry(hass)
        ent_to_remove = ent_reg.async_get_entity_id(
            DOMAIN, DOMAIN, UNIQUE_ID_TEMPLATE.format(key)
        )
        if ent_to_remove is not None:
            ent_reg.async_remove(ent_to_remove)

    async def async_set_variable(call: ServiceCall):
        """Set a variable."""
        key = call.data[CONF_KEY]
        value = call.data[CONF_VALUE]

        if variable_manager.async_get(key):
            _LOGGER.debug('Updating existing variable: %s ("%s")', key, value)
            async_dispatcher_send(hass, TOPIC_VARIABLE_SET.format(key), value)
        else:
            _LOGGER.debug('Creating new variable: %s ("%s")', key, value)
            await entity_component.async_add_entities([Variable(key, value)])

        variable_manager.async_set(key, value)

    for service, method, schema in [
        ("remove", async_remove_variable, REMOVE_VARIABLE_SCHEMA),
        ("set", async_set_variable, SET_VARIABLE_SCHEMA),
    ]:
        hass.services.async_register(DOMAIN, service, method, schema=schema)

    return True


class VariableStore(Store):
    """Define variable storage."""

    async def _async_migrate_func(self, old_version, old_data):
        """Migrate to the new version.

        Migrate storage to use format of collection helper.
        """
        return old_data


class VariableManager:
    """Define an object to manage variables."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        self._storage = VariableStore(hass, STORAGE_VERSION, STORAGE_KEY)
        self._variables = {}

    @callback
    def _async_save(self) -> None:
        """Save variables to storage."""
        self._storage.async_delay_save(lambda: self._variables, STORAGE_SAVE_DELAY)

    @callback
    def async_get(self, key: str) -> Union[str, None]:
        """Get a variable value. Returns None if the variable doesn't exist."""
        return self._variables.get(key, None)

    async def async_init(self) -> None:
        """Set up the manager."""
        variables = await self._storage.async_load()
        if variables:
            self._variables = variables

    @callback
    def async_set(self, key: str, value: str) -> None:
        """Remove a variable."""
        self._variables[key] = value
        self._async_save()

    @callback
    def async_remove(self, key: str) -> None:
        """Remove a variable."""
        self._variables.pop(key)
        self._async_save()


class Variable(Entity):
    """Represent a variable (a key/value pair)."""

    def __init__(self, key: str, value: str) -> None:
        """Initialize."""
        self._key = key
        self._value = value

    @property
    def name(self) -> str:
        """Return the entity name."""
        return self._key

    @property
    def should_poll(self) -> str:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return False

    @property
    def state(self) -> str:
        """Return the state of the entity."""
        return self._value

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the person."""
        return UNIQUE_ID_TEMPLATE.format(self._key)

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        @callback
        def async_update(value: str) -> None:
            """Update the entity."""
            self._value = value
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, TOPIC_VARIABLE_SET.format(self._key), async_update
            )
        )
