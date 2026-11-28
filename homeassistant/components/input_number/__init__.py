"""Support to set a numeric value from a slider or text box."""

from dataclasses import dataclass
import logging
from typing import override

import probatio

from homeassistant.components.number import DEVICE_CLASS_UNITS, DEVICE_CLASSES_SCHEMA
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_ID,
    CONF_MODE,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    SERVICE_RELOAD,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import collection, config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType, VolDictType

from .const import (
    ATTR_VALUE,
    CONF_INITIAL,
    CONF_MAX,
    CONF_MIN,
    CONF_STEP,
    DATA_INPUT_NUMBER,
    DOMAIN,
    SERVICE_DECREMENT,
    SERVICE_INCREMENT,
    SERVICE_SET_VALUE,
    InputNumberService,
    InputNumberServiceArgument,
)
from .entity import InputNumber
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)


MODE_SLIDER = "slider"
MODE_BOX = "box"

ATTR_MIN = "min"
ATTR_MAX = "max"
ATTR_STEP = "step"

__all__ = [
    "ATTR_MAX",
    "ATTR_MIN",
    "ATTR_STEP",
    "ATTR_VALUE",
    "CONF_INITIAL",
    "CONF_MAX",
    "CONF_MIN",
    "CONF_MODE",
    "CONF_NAME",
    "CONF_STEP",
    "CONF_UNIT_OF_MEASUREMENT",
    "DOMAIN",
    "SERVICE_DECREMENT",
    "SERVICE_INCREMENT",
    "SERVICE_RELOAD",
    "SERVICE_SET_VALUE",
    "STORAGE_FIELDS",
    "InputNumber",
    "InputNumberService",
    "InputNumberServiceArgument",
]


def _cv_input_number(cfg):
    """Configure validation helper for input number (probatio)."""
    minimum = cfg.get(CONF_MIN)
    maximum = cfg.get(CONF_MAX)
    if minimum >= maximum:
        raise probatio.Invalid(
            f"Maximum ({minimum}) is not greater than minimum ({maximum})"
        )
    state = cfg.get(CONF_INITIAL)
    if state is not None and (state < minimum or state > maximum):
        raise probatio.Invalid(
            f"Initial value {state} not in range {minimum}-{maximum}"
        )
    # Remove when number entities enforce valid units for their device class
    if (
        (device_class := cfg.get(CONF_DEVICE_CLASS)) is not None
        and (units := DEVICE_CLASS_UNITS.get(device_class)) is not None
        and (unit := cfg.get(CONF_UNIT_OF_MEASUREMENT)) not in units
    ):
        valid_units = sorted(str(valid) if valid else "no unit" for valid in units)
        raise probatio.Invalid(
            f"Unit of measurement '{unit}' is not valid for device class "
            f"'{device_class}'; expected one of {valid_units}"
        )
    return cfg


STORAGE_FIELDS: VolDictType = {
    probatio.Required(CONF_NAME): probatio.All(str, probatio.NonEmpty()),
    probatio.Required(CONF_MIN): probatio.Coerce(float),
    probatio.Required(CONF_MAX): probatio.Coerce(float),
    probatio.Optional(CONF_INITIAL): probatio.Coerce(float),
    probatio.Optional(CONF_STEP, default=1): probatio.All(
        probatio.Coerce(float), probatio.Range(min=1e-9)
    ),
    probatio.Optional(CONF_ICON): cv.icon,
    probatio.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    probatio.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    probatio.Optional(CONF_MODE, default=MODE_SLIDER): probatio.In(
        [MODE_BOX, MODE_SLIDER]
    ),
}

CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: cv.schema_with_slug_keys(
            probatio.All(
                {
                    probatio.Optional(CONF_NAME): cv.string,
                    probatio.Required(CONF_MIN): probatio.Coerce(float),
                    probatio.Required(CONF_MAX): probatio.Coerce(float),
                    probatio.Optional(CONF_INITIAL): probatio.Coerce(float),
                    probatio.Optional(CONF_STEP, default=1): probatio.All(
                        probatio.Coerce(float), probatio.Range(min=1e-9)
                    ),
                    probatio.Optional(CONF_ICON): cv.icon,
                    probatio.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
                    probatio.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
                    probatio.Optional(CONF_MODE, default=MODE_SLIDER): probatio.In(
                        [MODE_BOX, MODE_SLIDER]
                    ),
                },
                _cv_input_number,
            )
        )
    },
    extra=probatio.ALLOW_EXTRA,
)
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1


@dataclass(slots=True)
class InputNumberData:
    """Runtime data for the input_number integration."""

    component: EntityComponent[InputNumber]
    yaml_collection: collection.YamlCollection


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

    hass.data[DATA_INPUT_NUMBER] = InputNumberData(component, yaml_collection)

    async_setup_services(hass)
    return True


class NumberStorageCollection(collection.DictStorageCollection):
    """Input storage based collection."""

    SCHEMA = probatio.Schema(probatio.All(STORAGE_FIELDS, _cv_input_number))

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
