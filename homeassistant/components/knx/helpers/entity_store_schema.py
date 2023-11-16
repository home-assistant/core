"""KNX entity store schema."""
import voluptuous as vol

from homeassistant.components.switch import (
    DEVICE_CLASSES_SCHEMA as SWITCH_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.const import Platform
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import ENTITY_CATEGORIES_SCHEMA

from ..schema import ga_list_validator, sync_state_validator

BASE_ENTITY_SCHEMA = vol.Schema(
    {
        vol.Required("name"): str,
        vol.Required("device_id"): vol.Maybe(str),
        vol.Required("entity_category"): vol.Maybe(ENTITY_CATEGORIES_SCHEMA),
        vol.Required("sync_state"): sync_state_validator,
    }
)

SWITCH_SCHEMA = BASE_ENTITY_SCHEMA.extend(
    {
        vol.Required("device_class"): vol.Maybe(SWITCH_DEVICE_CLASSES_SCHEMA),
        vol.Required("invert"): bool,
        vol.Required("switch_address"): ga_list_validator,
        vol.Required("switch_state_address"): vol.Maybe(ga_list_validator),
        vol.Required("respond_to_read"): bool,
    }
)

ENTITY_STORE_DATA_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required("platform"): vol.Coerce(Platform),
            vol.Required("data"): dict,
        },
        extra=vol.ALLOW_EXTRA,
    ),
    cv.key_value_schemas(
        "platform",
        {
            Platform.SWITCH: vol.Schema(
                {vol.Required("data"): SWITCH_SCHEMA}, extra=vol.ALLOW_EXTRA
            )
        },
    ),
)

CREATE_ENTITY_BASE_SCHEMA = {
    vol.Required("platform"): str,
    vol.Required("data"): dict,  # validated by ENTITY_STORE_DATA_SCHEMA
}

UPDATE_ENTITY_BASE_SCHEMA = {
    vol.Required("unique_id"): str,
    **CREATE_ENTITY_BASE_SCHEMA,
}

DELETE_ENTITY_SCHEMA = {
    vol.Required("platform"): vol.Coerce(Platform),
    vol.Required("unique_id"): str,
}
