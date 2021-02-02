"""Component to count within automations."""
import logging
from typing import Dict, Optional

import voluptuous as vol

from homeassistant.const import (
    ATTR_EDITABLE,
    CONF_ICON,
    CONF_ID,
    CONF_MAXIMUM,
    CONF_MINIMUM,
    CONF_NAME,
)
from homeassistant.core import callback
from homeassistant.helpers import collection
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

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
SERVICE_CONFIGURE = "configure"

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

CREATE_FIELDS = {
    vol.Optional(CONF_ICON): cv.icon,
    vol.Optional(CONF_INITIAL, default=DEFAULT_INITIAL): cv.positive_int,
    vol.Required(CONF_NAME): vol.All(cv.string, vol.Length(min=1)),
    vol.Optional(CONF_MAXIMUM, default=None): vol.Any(None, vol.Coerce(int)),
    vol.Optional(CONF_MINIMUM, default=None): vol.Any(None, vol.Coerce(int)),
    vol.Optional(CONF_RESTORE, default=True): cv.boolean,
    vol.Optional(CONF_STEP, default=DEFAULT_STEP): cv.positive_int,
}

UPDATE_FIELDS = {
    vol.Optional(CONF_ICON): cv.icon,
    vol.Optional(CONF_INITIAL): cv.positive_int,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_MAXIMUM): vol.Any(None, vol.Coerce(int)),
    vol.Optional(CONF_MINIMUM): vol.Any(None, vol.Coerce(int)),
    vol.Optional(CONF_RESTORE): cv.boolean,
    vol.Optional(CONF_STEP): cv.positive_int,
}


def _none_to_empty_dict(value):
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


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up the counters."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    id_manager = collection.IDManager()

    yaml_collection = collection.YamlCollection(
        logging.getLogger(f"{__name__}.yaml_collection"), id_manager
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, yaml_collection, Counter.from_yaml
    )

    storage_collection = CounterStorageCollection(
        Store(hass, STORAGE_VERSION, STORAGE_KEY),
        logging.getLogger(f"{__name__}.storage_collection"),
        id_manager,
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, storage_collection, Counter
    )

    await yaml_collection.async_load(
        [{CONF_ID: id_, **(conf or {})} for id_, conf in config.get(DOMAIN, {}).items()]
    )
    await storage_collection.async_load()

    collection.StorageCollectionWebsocket(
        storage_collection, DOMAIN, DOMAIN, CREATE_FIELDS, UPDATE_FIELDS
    ).async_setup(hass)

    component.async_register_entity_service(SERVICE_INCREMENT, {}, "async_increment")
    component.async_register_entity_service(SERVICE_DECREMENT, {}, "async_decrement")
    component.async_register_entity_service(SERVICE_RESET, {}, "async_reset")
    component.async_register_entity_service(
        SERVICE_CONFIGURE,
        {
            vol.Optional(ATTR_MINIMUM): vol.Any(None, vol.Coerce(int)),
            vol.Optional(ATTR_MAXIMUM): vol.Any(None, vol.Coerce(int)),
            vol.Optional(ATTR_STEP): cv.positive_int,
            vol.Optional(ATTR_INITIAL): cv.positive_int,
            vol.Optional(VALUE): cv.positive_int,
        },
        "async_configure",
    )

    return True


class CounterStorageCollection(collection.StorageCollection):
    """Input storage based collection."""

    CREATE_SCHEMA = vol.Schema(CREATE_FIELDS)
    UPDATE_SCHEMA = vol.Schema(UPDATE_FIELDS)

    async def _process_create_data(self, data: Dict) -> Dict:
        """Validate the config is valid."""
        return self.CREATE_SCHEMA(data)

    @callback
    def _get_suggested_id(self, info: Dict) -> str:
        """Suggest an ID based on the config."""
        return info[CONF_NAME]

    async def _update_data(self, data: dict, update_data: Dict) -> Dict:
        """Return a new updated data object."""
        update_data = self.UPDATE_SCHEMA(update_data)
        return {**data, **update_data}


class Counter(RestoreEntity):
    """Representation of a counter."""

    def __init__(self, config: Dict):
        """Initialize a counter."""
        self._config: Dict = config
        self._state: Optional[int] = config[CONF_INITIAL]
        self.editable: bool = True

    @classmethod
    def from_yaml(cls, config: Dict) -> "Counter":
        """Create counter instance from yaml config."""
        counter = cls(config)
        counter.editable = False
        counter.entity_id = ENTITY_ID_FORMAT.format(config[CONF_ID])
        return counter

    @property
    def should_poll(self) -> bool:
        """If entity should be polled."""
        return False

    @property
    def name(self) -> Optional[str]:
        """Return name of the counter."""
        return self._config.get(CONF_NAME)

    @property
    def icon(self) -> Optional[str]:
        """Return the icon to be used for this entity."""
        return self._config.get(CONF_ICON)

    @property
    def state(self) -> Optional[int]:
        """Return the current value of the counter."""
        return self._state

    @property
    def state_attributes(self) -> Dict:
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
    def unique_id(self) -> Optional[str]:
        """Return unique id of the entity."""
        return self._config[CONF_ID]

    def compute_next_state(self, state) -> int:
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
        if self._config[CONF_RESTORE]:
            state = await self.async_get_last_state()
            if state is not None:
                self._state = self.compute_next_state(int(state.state))
                self._config[CONF_INITIAL] = state.attributes.get(ATTR_INITIAL)
                self._config[CONF_MAXIMUM] = state.attributes.get(ATTR_MAXIMUM)
                self._config[CONF_MINIMUM] = state.attributes.get(ATTR_MINIMUM)
                self._config[CONF_STEP] = state.attributes.get(ATTR_STEP)

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
    def async_configure(self, **kwargs) -> None:
        """Change the counter's settings with a service."""
        new_state = kwargs.pop(VALUE, self._state)
        self._config = {**self._config, **kwargs}
        self._state = self.compute_next_state(new_state)
        self.async_write_ha_state()

    async def async_update_config(self, config: Dict) -> None:
        """Change the counter's settings WS CRUD."""
        self._config = config
        self._state = self.compute_next_state(self._state)
        self.async_write_ha_state()
