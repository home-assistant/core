"""Schemas used by insteon component."""

from typing import Dict

import voluptuous as vol

from homeassistant.const import (
    CONF_ADDRESS,
    CONF_ENTITY_ID,
    CONF_HOST,
    CONF_PLATFORM,
    CONF_PORT,
    ENTITY_MATCH_ALL,
)
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_CAT,
    CONF_DIM_STEPS,
    CONF_FIRMWARE,
    CONF_HOUSECODE,
    CONF_HUB_PASSWORD,
    CONF_HUB_USERNAME,
    CONF_HUB_VERSION,
    CONF_IP_PORT,
    CONF_OVERRIDE,
    CONF_PLM_HUB_MSG,
    CONF_PRODUCT_KEY,
    CONF_SUBCAT,
    CONF_UNITCODE,
    CONF_X10,
    CONF_X10_ALL_LIGHTS_OFF,
    CONF_X10_ALL_LIGHTS_ON,
    CONF_X10_ALL_UNITS_OFF,
    DOMAIN,
    HOUSECODES,
    SRV_ALL_LINK_GROUP,
    SRV_ALL_LINK_MODE,
    SRV_CONTROLLER,
    SRV_HOUSECODE,
    SRV_LOAD_DB_RELOAD,
    SRV_RESPONDER,
)


def set_default_port(schema: Dict) -> Dict:
    """Set the default port based on the Hub version."""
    # If the ip_port is found do nothing
    # If it is not found the set the default
    ip_port = schema.get(CONF_IP_PORT)
    if not ip_port:
        hub_version = schema.get(CONF_HUB_VERSION)
        # Found hub_version but not ip_port
        schema[CONF_IP_PORT] = 9761 if hub_version == 1 else 25105
    return schema


CONF_DEVICE_OVERRIDE_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_ADDRESS): cv.string,
            vol.Optional(CONF_CAT): cv.byte,
            vol.Optional(CONF_SUBCAT): cv.byte,
            vol.Optional(CONF_FIRMWARE): cv.byte,
            vol.Optional(CONF_PRODUCT_KEY): cv.byte,
            vol.Optional(CONF_PLATFORM): cv.string,
        }
    ),
)


CONF_X10_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_HOUSECODE): cv.string,
            vol.Required(CONF_UNITCODE): vol.Range(min=1, max=16),
            vol.Required(CONF_PLATFORM): cv.string,
            vol.Optional(CONF_DIM_STEPS): vol.Range(min=2, max=255),
        }
    )
)


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.deprecated(CONF_X10_ALL_UNITS_OFF),
            cv.deprecated(CONF_X10_ALL_LIGHTS_ON),
            cv.deprecated(CONF_X10_ALL_LIGHTS_OFF),
            vol.Schema(
                {
                    vol.Exclusive(
                        CONF_PORT, "plm_or_hub", msg=CONF_PLM_HUB_MSG
                    ): cv.string,
                    vol.Exclusive(
                        CONF_HOST, "plm_or_hub", msg=CONF_PLM_HUB_MSG
                    ): cv.string,
                    vol.Optional(CONF_IP_PORT): cv.port,
                    vol.Optional(CONF_HUB_USERNAME): cv.string,
                    vol.Optional(CONF_HUB_PASSWORD): cv.string,
                    vol.Optional(CONF_HUB_VERSION, default=2): vol.In([1, 2]),
                    vol.Optional(CONF_OVERRIDE): vol.All(
                        cv.ensure_list_csv, [CONF_DEVICE_OVERRIDE_SCHEMA]
                    ),
                    vol.Optional(CONF_X10): vol.All(
                        cv.ensure_list_csv, [CONF_X10_SCHEMA]
                    ),
                },
                extra=vol.ALLOW_EXTRA,
                required=True,
            ),
            cv.has_at_least_one_key(CONF_PORT, CONF_HOST),
            set_default_port,
        )
    },
    extra=vol.ALLOW_EXTRA,
)


ADD_ALL_LINK_SCHEMA = vol.Schema(
    {
        vol.Required(SRV_ALL_LINK_GROUP): vol.Range(min=0, max=255),
        vol.Required(SRV_ALL_LINK_MODE): vol.In([SRV_CONTROLLER, SRV_RESPONDER]),
    }
)


DEL_ALL_LINK_SCHEMA = vol.Schema(
    {vol.Required(SRV_ALL_LINK_GROUP): vol.Range(min=0, max=255)}
)


LOAD_ALDB_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): vol.Any(cv.entity_id, ENTITY_MATCH_ALL),
        vol.Optional(SRV_LOAD_DB_RELOAD, default=False): cv.boolean,
    }
)


PRINT_ALDB_SCHEMA = vol.Schema({vol.Required(CONF_ENTITY_ID): cv.entity_id})


X10_HOUSECODE_SCHEMA = vol.Schema({vol.Required(SRV_HOUSECODE): vol.In(HOUSECODES)})


TRIGGER_SCENE_SCHEMA = vol.Schema(
    {vol.Required(SRV_ALL_LINK_GROUP): vol.Range(min=0, max=255)}
)
