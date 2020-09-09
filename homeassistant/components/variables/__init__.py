"""The Variables integration."""
from dataclasses import dataclass
import logging
from typing import Dict, Optional

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

CONF_ATTRS = "attributes"
CONF_KEY = "key"
CONF_VALUE = "value"

REMOVE_VARIABLE_SCHEMA = vol.Schema({vol.Required(CONF_KEY): cv.string})
SET_VARIABLE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_KEY): cv.string,
        vol.Required(CONF_VALUE): cv.string,
        vol.Optional(CONF_ATTRS): dict,
    }
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
        attributes = call.data.get(CONF_ATTRS)

        variable = await variable_manager.async_set(key, value, attributes=attributes)

        ent_reg = await entity_registry.async_get_registry(hass)
        existing_ent = ent_reg.async_get_entity_id(
            DOMAIN, DOMAIN, UNIQUE_ID_TEMPLATE.format(key)
        )
        if existing_ent:
            async_dispatcher_send(hass, TOPIC_VARIABLE_SET.format(key))
        else:
            await entity_component.async_add_entities([VariableEntity(variable)])

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


@dataclass
class Variable:
    """Define a variable."""

    key: str
    value: str
    attributes: Optional[dict]


class VariableManager:
    """Define an object to manage variables."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        self._storage: VariableStore = VariableStore(hass, STORAGE_VERSION, STORAGE_KEY)
        self._variables: Dict[str, Variable] = {}

    @callback
    def _async_prep_save_data(self) -> dict:
        """Return data in the format to save."""
        return {
            key: {CONF_VALUE: variable.value, CONF_ATTRS: variable.attributes}
            for key, variable in self._variables.items()
        }

    @callback
    def _async_save(self) -> None:
        """Save variables to storage."""
        self._storage.async_delay_save(self._async_prep_save_data, STORAGE_SAVE_DELAY)

    @callback
    async def async_init(self) -> None:
        """Set up the manager."""
        raw = await self._storage.async_load()

        if not raw:
            return

        for key, data in raw.items():
            self._variables[key] = Variable(
                key, data[CONF_VALUE], attributes=data.get(CONF_ATTRS)
            )

    @callback
    def async_set(
        self, key: str, value: str, attributes: Optional[dict] = None
    ) -> Variable:
        """Set a variable and return it."""
        if key in self._variables:
            _LOGGER.debug('Updating existing variable: %s ("%s")', key, value)
            variable = self._variables[key]
            variable.key = key
            variable.value = value
            variable.attributes = attributes
        else:
            _LOGGER.debug('Creating new variable: %s ("%s")', key, value)
            self._variables[key] = Variable(key, value, attributes=attributes)

        self._async_save()

        return self._variables[key]

    @callback
    def async_remove(self, key: str) -> None:
        """Remove a variable."""
        _LOGGER.debug("Removing variable: %s", key)

        if key not in self._variables:
            _LOGGER.warning("Can't delete variable that doesn't exist: %s", key)
            return

        self._variables.pop(key)
        self._async_save()


class VariableEntity(Entity):
    """Represent a variable (a key/value pair)."""

    def __init__(self, variable: Variable) -> None:
        """Initialize."""
        self._variable = variable

    @property
    def device_state_attributes(self) -> dict:
        """Return the state attributes."""
        return self._variable.attributes

    @property
    def name(self) -> str:
        """Return the entity name."""
        return self._variable.key

    @property
    def should_poll(self) -> str:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return False

    @property
    def state(self) -> str:
        """Return the state of the entity."""
        return self._variable.value

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the person."""
        return UNIQUE_ID_TEMPLATE.format(self._variable.key)

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        @callback
        def async_update() -> None:
            """Update the entity."""
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, TOPIC_VARIABLE_SET.format(self._variable.key), async_update
            )
        )
