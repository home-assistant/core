"""Component to count within automations."""

from __future__ import annotations

import logging
from typing import Any, Self

import voluptuous as vol

from homeassistant.const import (
    ATTR_EDITABLE,
    CONF_ICON,
    CONF_ID,
    CONF_MAXIMUM,
    CONF_MINIMUM,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import collection, config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType, VolDictType

_LOGGER = logging.getLogger(__name__)

ATTR_INITIAL = "initial"
ATTR_STEP = "step"
ATTR_MINIMUM = "minimum"
ATTR_MAXIMUM = "maximum"
VALUE = "value"

CONF_INITIAL = "initial"
CONF_RESTORE = "restore"
CONF_STEP = "step"

DEFAULT_INITIAL = 0
DEFAULT_STEP = 1
DOMAIN = "counter"

ENTITY_ID_FORMAT = DOMAIN + ".{}"

SERVICE_DECREMENT = "decrement"
SERVICE_INCREMENT = "increment"
SERVICE_RESET = "reset"
SERVICE_SET_VALUE = "set_value"

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

STORAGE_FIELDS: VolDictType = {
    vol.Optional(CONF_ICON): cv.icon,
    vol.Optional(CONF_INITIAL, default=DEFAULT_INITIAL): cv.positive_int,
    vol.Required(CONF_NAME): vol.All(cv.string, vol.Length(min=1)),
    vol.Optional(CONF_MAXIMUM, default=None): vol.Any(None, vol.Coerce(int)),
    vol.Optional(CONF_MINIMUM, default=None): vol.Any(None, vol.Coerce(int)),
    vol.Optional(CONF_RESTORE, default=True): cv.boolean,
    vol.Optional(CONF_STEP, default=DEFAULT_STEP): cv.positive_int,
}


def _none_to_empty_dict[_T](value: _T | None) -> _T | dict[str, Any]:
    if value is None:
        return {}
    return value


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: cv.schema_with_slug_keys(
            vol.All(
                _none_to_empty_dict,
                {
                    vol.Optional(CONF_ICON): cv.icon,
                    vol.Optional(
                        CONF_INITIAL, default=DEFAULT_INITIAL
                    ): cv.positive_int,
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Optional(CONF_MAXIMUM, default=None): vol.Any(
                        None, vol.Coerce(int)
                    ),
                    vol.Optional(CONF_MINIMUM, default=None): vol.Any(
                        None, vol.Coerce(int)
                    ),
                    vol.Optional(CONF_RESTORE, default=True): cv.boolean,
                    vol.Optional(CONF_STEP, default=DEFAULT_STEP): cv.positive_int,
                },
            )
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the counters."""
    component = EntityComponent[Counter](_LOGGER, DOMAIN, hass)
    id_manager = collection.IDManager()

    yaml_collection = collection.YamlCollection(
        logging.getLogger(f"{__name__}.yaml_collection"), id_manager
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, yaml_collection, Counter
    )

    storage_collection = CounterStorageCollection(
        Store(hass, STORAGE_VERSION, STORAGE_KEY),
        id_manager,
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, storage_collection, Counter
    )

    await yaml_collection.async_load(
        [{CONF_ID: id_, **(conf or {})} for id_, conf in config.get(DOMAIN, {}).items()]
    )
    await storage_collection.async_load()

    collection.DictStorageCollectionWebsocket(
        storage_collection, DOMAIN, DOMAIN, STORAGE_FIELDS, STORAGE_FIELDS
    ).async_setup(hass)

    component.async_register_entity_service(SERVICE_INCREMENT, None, "async_increment")
    component.async_register_entity_service(SERVICE_DECREMENT, None, "async_decrement")
    component.async_register_entity_service(SERVICE_RESET, None, "async_reset")
    component.async_register_entity_service(
        SERVICE_SET_VALUE,
        {vol.Required(VALUE): cv.positive_int},
        "async_set_value",
    )

    return True


class CounterStorageCollection(collection.DictStorageCollection):
    """Input storage based collection."""

    CREATE_UPDATE_SCHEMA = vol.Schema(STORAGE_FIELDS)

    async def _process_create_data(self, data: dict) -> dict:
        """Validate the config is valid."""
        return self.CREATE_UPDATE_SCHEMA(data)  # type: ignore[no-any-return]

    @callback
    def _get_suggested_id(self, info: dict) -> str:
        """Suggest an ID based on the config."""
        return info[CONF_NAME]  # type: ignore[no-any-return]

    async def _update_data(self, item: dict, update_data: dict) -> dict:
        """Return a new updated data object."""
        update_data = self.CREATE_UPDATE_SCHEMA(update_data)
        return {CONF_ID: item[CONF_ID]} | update_data


class Counter(collection.CollectionEntity, RestoreEntity):
    """Representation of a counter."""

    _attr_should_poll: bool = False
    editable: bool

    def __init__(self, config: ConfigType) -> None:
        """Initialize a counter."""
        self._config: ConfigType = config
        self._state: int | None = config[CONF_INITIAL]

    @classmethod
    def from_storage(cls, config: ConfigType) -> Self:
        """Create counter instance from storage."""
        counter = cls(config)
        counter.editable = True
        return counter

    @classmethod
    def from_yaml(cls, config: ConfigType) -> Self:
        """Create counter instance from yaml config."""
        counter = cls(config)
        counter.editable = False
        counter.entity_id = ENTITY_ID_FORMAT.format(config[CONF_ID])
        return counter

    @property
    def name(self) -> str | None:
        """Return name of the counter."""
        return self._config.get(CONF_NAME)

    @property
    def icon(self) -> str | None:
        """Return the icon to be used for this entity."""
        return self._config.get(CONF_ICON)

    @property
    def state(self) -> int | None:
        """Return the current value of the counter."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        ret = {
            ATTR_EDITABLE: self.editable,
            ATTR_INITIAL: self._config[CONF_INITIAL],
            ATTR_STEP: self._config[CONF_STEP],
        }
        if self._config[CONF_MINIMUM] is not None:
            ret[CONF_MINIMUM] = self._config[CONF_MINIMUM]
        if self._config[CONF_MAXIMUM] is not None:
            ret[CONF_MAXIMUM] = self._config[CONF_MAXIMUM]
        return ret

    @property
    def unique_id(self) -> str | None:
        """Return unique id of the entity."""
        return self._config[CONF_ID]  # type: ignore[no-any-return]

    def compute_next_state(self, state: int | None) -> int | None:
        """Keep the state within the range of min/max values."""
        if self._config[CONF_MINIMUM] is not None:
            state = max(self._config[CONF_MINIMUM], state)
        if self._config[CONF_MAXIMUM] is not None:
            state = min(self._config[CONF_MAXIMUM], state)

        return state

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to Home Assistant."""
        await super().async_added_to_hass()
        # __init__ will set self._state to self._initial, only override
        # if needed.
        if (
            self._config[CONF_RESTORE]
            and (state := await self.async_get_last_state()) is not None
        ):
            self._state = self.compute_next_state(int(state.state))

    @callback
    def async_decrement(self) -> None:
        """Decrement the counter."""
        self._state = self.compute_next_state(self._state - self._config[CONF_STEP])
        self.async_write_ha_state()

    @callback
    def async_increment(self) -> None:
        """Increment a counter."""
        self._state = self.compute_next_state(self._state + self._config[CONF_STEP])
        self.async_write_ha_state()

    @callback
    def async_reset(self) -> None:
        """Reset a counter."""
        self._state = self.compute_next_state(self._config[CONF_INITIAL])
        self.async_write_ha_state()

    @callback
    def async_set_value(self, value: int) -> None:
        """Set counter to value."""
        if (maximum := self._config.get(CONF_MAXIMUM)) is not None and value > maximum:
            raise ValueError(
                f"Value {value} for {self.entity_id} exceeding the maximum value of {maximum}"
            )

        if (minimum := self._config.get(CONF_MINIMUM)) is not None and value < minimum:
            raise ValueError(
                f"Value {value} for {self.entity_id} exceeding the minimum value of {minimum}"
            )

        if (step := self._config.get(CONF_STEP)) is not None and value % step != 0:
            raise ValueError(
                f"Value {value} for {self.entity_id} is not a multiple of the step size {step}"
            )

        self._state = value
        self.async_write_ha_state()

    async def async_update_config(self, config: ConfigType) -> None:
        """Change the counter's settings WS CRUD."""
        self._config = config
        self._state = self.compute_next_state(self._state)
        self.async_write_ha_state()
