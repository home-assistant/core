"""KNX entity store schema."""

import voluptuous as vol

from homeassistant.const import (
    CONF_ENTITY_CATEGORY,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_PLATFORM,
    Platform,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import ENTITY_CATEGORIES_SCHEMA
from homeassistant.helpers.typing import VolDictType, VolSchemaType

from ..const import (
    CONF_INVERT,
    CONF_RESPOND_TO_READ,
    CONF_SYNC_STATE,
    DOMAIN,
    SUPPORTED_PLATFORMS_UI,
)
from ..validation import sync_state_validator
from .const import CONF_DATA, CONF_DEVICE_INFO, CONF_ENTITY, CONF_GA_SWITCH
from .knx_selector import GASelector

BASE_ENTITY_SCHEMA = vol.All(
    {
        vol.Optional(CONF_NAME, default=None): vol.Maybe(str),
        vol.Optional(CONF_DEVICE_INFO, default=None): vol.Maybe(str),
        vol.Optional(CONF_ENTITY_CATEGORY, default=None): vol.Any(
            ENTITY_CATEGORIES_SCHEMA, vol.SetTo(None)
        ),
    },
    vol.Any(
        vol.Schema(
            {
                vol.Required(CONF_NAME): vol.All(str, vol.IsTrue()),
            },
            extra=vol.ALLOW_EXTRA,
        ),
        vol.Schema(
            {
                vol.Required(CONF_DEVICE_INFO): str,
            },
            extra=vol.ALLOW_EXTRA,
        ),
        msg="One of `Device` or `Name` is required",
    ),
)

SWITCH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY): BASE_ENTITY_SCHEMA,
        vol.Required(DOMAIN): {
            vol.Optional(CONF_INVERT, default=False): bool,
            vol.Required(CONF_GA_SWITCH): GASelector(write_required=True),
            vol.Optional(CONF_RESPOND_TO_READ, default=False): bool,
            vol.Optional(CONF_SYNC_STATE, default=True): sync_state_validator,
        },
    }
)


ENTITY_STORE_DATA_SCHEMA: VolSchemaType = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_PLATFORM): vol.All(
                vol.Coerce(Platform),
                vol.In(SUPPORTED_PLATFORMS_UI),
            ),
            vol.Required(CONF_DATA): dict,
        },
        extra=vol.ALLOW_EXTRA,
    ),
    cv.key_value_schemas(
        CONF_PLATFORM,
        {
            Platform.SWITCH: vol.Schema(
                {vol.Required(CONF_DATA): SWITCH_SCHEMA}, extra=vol.ALLOW_EXTRA
            ),
        },
    ),
)

CREATE_ENTITY_BASE_SCHEMA: VolDictType = {
    vol.Required(CONF_PLATFORM): str,
    vol.Required(CONF_DATA): dict,  # validated by ENTITY_STORE_DATA_SCHEMA for platform
}

UPDATE_ENTITY_BASE_SCHEMA = {
    vol.Required(CONF_ENTITY_ID): str,
    **CREATE_ENTITY_BASE_SCHEMA,
}
