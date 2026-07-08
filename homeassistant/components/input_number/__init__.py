"""Support to set a numeric value from a slider or text box."""

from contextlib import suppress
import logging
from typing import Any, Self, override

import voluptuous as vol

from homeassistant.components.number import NumberEntity
from homeassistant.const import (  # noqa: F401
    ATTR_EDITABLE,
    ATTR_MODE,
    CONF_ICON,
    CONF_ID,
    CONF_MODE,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    SERVICE_RELOAD,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import collection, config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
import homeassistant.helpers.service
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType, VolDictType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "input_number"

CONF_INITIAL = "initial"
CONF_MIN = "min"
CONF_MAX = "max"
CONF_STEP = "step"

MODE_SLIDER = "slider"
MODE_BOX = "box"

ATTR_INITIAL = "initial"
ATTR_VALUE = "value"
ATTR_MIN = "min"
ATTR_MAX = "max"
ATTR_STEP = "step"

SERVICE_SET_VALUE = "set_value"
SERVICE_INCREMENT = "increment"
SERVICE_DECREMENT = "decrement"


def _cv_input_number(cfg):
    """Configure validation helper for input number (voluptuous)."""
    minimum = cfg.get(CONF_MIN)
    maximum = cfg.get(CONF_MAX)
    if minimum >= maximum:
        raise vol.Invalid(
            f"Maximum ({minimum}) is not greater than minimum ({maximum})"
        )
    state = cfg.get(CONF_INITIAL)
    if state is not None and (state < minimum or state > maximum):
        raise vol.Invalid(f"Initial value {state} not in range {minimum}-{maximum}")
    return cfg


STORAGE_FIELDS: VolDictType = {
    vol.Required(CONF_NAME): vol.All(str, vol.Length(min=1)),
    vol.Required(CONF_MIN): vol.Coerce(float),
    vol.Required(CONF_MAX): vol.Coerce(float),
    vol.Optional(CONF_INITIAL): vol.Coerce(float),
    vol.Optional(CONF_STEP, default=1): vol.All(vol.Coerce(float), vol.Range(min=1e-9)),
    vol.Optional(CONF_ICON): cv.icon,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    vol.Optional(CONF_MODE, default=MODE_SLIDER): vol.In([MODE_BOX, MODE_SLIDER]),
}

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: cv.schema_with_slug_keys(
            vol.All(
                {
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Required(CONF_MIN): vol.Coerce(float),
                    vol.Required(CONF_MAX): vol.Coerce(float),
                    vol.Optional(CONF_INITIAL): vol.Coerce(float),
                    vol.Optional(CONF_STEP, default=1): vol.All(
                        vol.Coerce(float), vol.Range(min=1e-9)
                    ),
                    vol.Optional(CONF_ICON): cv.icon,
                    vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
                    vol.Optional(CONF_MODE, default=MODE_SLIDER): vol.In(
                        [MODE_BOX, MODE_SLIDER]
                    ),
                },
                _cv_input_number,
            )
        )
    },
    extra=vol.ALLOW_EXTRA,
)
RELOAD_SERVICE_SCHEMA = vol.Schema({})
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up an input slider."""
    component = EntityComponent[InputNumber](_LOGGER, DOMAIN, hass)

    id_manager = collection.IDManager()

    yaml_collection = collection.YamlCollection(
        logging.getLogger(f"{__name__}.yaml_collection"), id_manager
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, yaml_collection, InputNumber
    )

    storage_collection = NumberStorageCollection(
        Store(hass, STORAGE_VERSION, STORAGE_KEY),
        id_manager,
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, storage_collection, InputNumber
    )

    await yaml_collection.async_load(
        [{CONF_ID: id_, **(conf or {})} for id_, conf in config.get(DOMAIN, {}).items()]
    )
    await storage_collection.async_load()

    collection.DictStorageCollectionWebsocket(
        storage_collection, DOMAIN, DOMAIN, STORAGE_FIELDS, STORAGE_FIELDS
    ).async_setup(hass)

    async def reload_service_handler(service_call: ServiceCall) -> None:
        """Reload yaml entities."""
        conf = await component.async_prepare_reload(skip_reset=True)
        await yaml_collection.async_load(
            [{CONF_ID: id_, **conf} for id_, conf in conf.get(DOMAIN, {}).items()]
        )

    homeassistant.helpers.service.async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_RELOAD,
        reload_service_handler,
        schema=RELOAD_SERVICE_SCHEMA,
    )

    component.async_register_entity_service(
        SERVICE_SET_VALUE,
        {vol.Required(ATTR_VALUE): vol.Coerce(float)},
        "async_set_native_value",
    )

    component.async_register_entity_service(SERVICE_INCREMENT, None, "async_increment")

    component.async_register_entity_service(SERVICE_DECREMENT, None, "async_decrement")

    return True


class NumberStorageCollection(collection.DictStorageCollection):
    """Input storage based collection."""

    SCHEMA = vol.Schema(vol.All(STORAGE_FIELDS, _cv_input_number))

    @override
    async def _process_create_data(self, data: dict) -> dict:
        """Validate the config is valid."""
        return self.SCHEMA(data)

    @callback
    @override
    def _get_suggested_id(self, info: dict) -> str:
        """Suggest an ID based on the config."""
        return info[CONF_NAME]

    @override
    async def _async_load_data(self) -> collection.SerializedStorageCollection | None:
        """Load the data.

        A past bug caused frontend to add initial value to all input numbers.
        This drops that.
        """
        data = await super()._async_load_data()

        if data is None:
            return data

        for number in data["items"]:
            number.pop(CONF_INITIAL, None)

        return data

    @override
    async def _update_data(self, item: dict, update_data: dict) -> dict:
        """Return a new updated data object."""
        update_data = self.SCHEMA(update_data)
        return {CONF_ID: item[CONF_ID]} | update_data


# pylint: disable-next=home-assistant-enforce-class-module
class InputNumber(collection.CollectionEntity, NumberEntity, RestoreEntity):
    """Representation of a slider."""

    _unrecorded_attributes = frozenset({ATTR_EDITABLE})

    _attr_should_poll = False
    editable: bool

    def __init__(self, config: ConfigType) -> None:
        """Initialize an input number."""
        self._initial_value: float | None = config.get(CONF_INITIAL)
        self._attr_native_value = self._initial_value
        self._update_config_attributes(config)

    def _update_config_attributes(self, config: ConfigType) -> None:
        """Update attributes based on the config."""
        self._attr_icon = config.get(CONF_ICON)
        self._attr_mode = config[CONF_MODE]
        self._attr_name = config.get(CONF_NAME)
        self._attr_native_min_value = config[CONF_MIN]
        self._attr_native_max_value = config[CONF_MAX]
        self._attr_native_step = config[CONF_STEP]
        self._attr_unique_id = config[CONF_ID]
        self._attr_native_unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)

    @classmethod
    @override
    def from_storage(cls, config: ConfigType) -> Self:
        """Return entity instance initialized from storage."""
        input_num = cls(config)
        input_num.editable = True
        return input_num

    @classmethod
    @override
    def from_yaml(cls, config: ConfigType) -> Self:
        """Return entity instance initialized from yaml."""
        input_num = cls(config)
        input_num.entity_id = f"{DOMAIN}.{config[CONF_ID]}"
        input_num.editable = False
        return input_num

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            ATTR_INITIAL: self._initial_value,
            ATTR_EDITABLE: self.editable,
        }

    @override
    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        if self._attr_native_value is not None:
            return

        value: float | None = None
        if state := await self.async_get_last_state():
            with suppress(ValueError):
                value = float(state.state)

        # Check against None because value can be 0
        if (
            value is not None
            and self.native_min_value <= value <= self.native_max_value
        ):
            self._attr_native_value = value
        else:
            self._attr_native_value = self.native_min_value

    @override
    async def async_set_native_value(self, value):
        """Set new value."""
        num_value = float(value)

        if num_value < self.native_min_value or num_value > self.native_max_value:
            raise vol.Invalid(
                f"Invalid value for {self.entity_id}: {value} (range "
                f"{self.native_min_value} - {self.native_max_value})"
            )

        self._attr_native_value = num_value
        self.async_write_ha_state()

    async def async_increment(self):
        """Increment value."""
        await self.async_set_native_value(
            min(self._attr_native_value + self.native_step, self.native_max_value)
        )

    async def async_decrement(self):
        """Decrement value."""
        await self.async_set_native_value(
            max(self._attr_native_value - self.native_step, self.native_min_value)
        )

    @override
    async def async_update_config(self, config: ConfigType) -> None:
        """Handle when the config is updated."""
        self._update_config_attributes(config)
        # just in case min/max values changed
        if self._attr_native_value is None:
            return
        self._attr_native_value = min(self._attr_native_value, self.native_max_value)
        self._attr_native_value = max(self._attr_native_value, self.native_min_value)
        self.async_write_ha_state()
