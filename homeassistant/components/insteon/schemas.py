"""Schemas used by insteon component."""

from __future__ import annotations

from pyinsteon.constants import HC_LOOKUP
import voluptuous as vol

from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DEVICE,
    CONF_ENTITY_ID,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PLATFORM,
    CONF_PORT,
    CONF_USERNAME,
    ENTITY_MATCH_ALL,
)
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_CAT,
    CONF_DIM_STEPS,
    CONF_HOUSECODE,
    CONF_HUB_VERSION,
    CONF_SUBCAT,
    CONF_UNITCODE,
    HOUSECODES,
    PORT_HUB_V1,
    PORT_HUB_V2,
    SRV_ALL_LINK_GROUP,
    SRV_ALL_LINK_MODE,
    SRV_CONTROLLER,
    SRV_HOUSECODE,
    SRV_LOAD_DB_RELOAD,
    SRV_RESPONDER,
    X10_PLATFORMS,
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


ADD_DEFAULT_LINKS_SCHEMA = vol.Schema({vol.Required(CONF_ENTITY_ID): cv.entity_id})


def build_device_override_schema(
    address=vol.UNDEFINED,
    cat=vol.UNDEFINED,
    subcat=vol.UNDEFINED,
    firmware=vol.UNDEFINED,
):
    """Build the device override schema for config flow."""
    return vol.Schema(
        {
            vol.Required(CONF_ADDRESS, default=address): str,
            vol.Optional(CONF_CAT, default=cat): str,
            vol.Optional(CONF_SUBCAT, default=subcat): str,
        }
    )


def build_x10_schema(
    housecode=vol.UNDEFINED,
    unitcode=vol.UNDEFINED,
    platform=vol.UNDEFINED,
    dim_steps=22,
):
    """Build the X10 schema for config flow."""
    if platform == "light":
        dim_steps_schema = vol.Required(CONF_DIM_STEPS, default=dim_steps)
    else:
        dim_steps_schema = vol.Optional(CONF_DIM_STEPS, default=dim_steps)
    return vol.Schema(
        {
            vol.Required(CONF_HOUSECODE, default=housecode): vol.In(HC_LOOKUP.keys()),
            vol.Required(CONF_UNITCODE, default=unitcode): vol.In(range(1, 17)),
            vol.Required(CONF_PLATFORM, default=platform): vol.In(X10_PLATFORMS),
            dim_steps_schema: vol.Range(min=0, max=255),
        }
    )


def _find_likely_port(ports):
    """Return the most likely USB port for a PLM."""
    test_strings = ["FTDI", "0403:6001", "10BF:"]
    for port, name in ports.items():
        for test_string in test_strings:
            if test_string in name:
                return port
    return vol.UNDEFINED


def build_plm_schema(ports: dict[str, str], device=vol.UNDEFINED):
    """Build the PLM schema for config flow."""
    if not device or device == vol.UNDEFINED:
        device = _find_likely_port(ports)
    return vol.Schema({vol.Required(CONF_DEVICE, default=device): vol.In(ports)})


def build_plm_manual_schema(device=vol.UNDEFINED):
    """Build the manual PLM schema for config flow."""
    return vol.Schema({vol.Required(CONF_DEVICE, default=device): str})


def build_hub_schema(
    hub_version,
    host=vol.UNDEFINED,
    port=vol.UNDEFINED,
    username=vol.UNDEFINED,
    password=vol.UNDEFINED,
):
    """Build the Hub schema for config flow."""
    if port == vol.UNDEFINED:
        port = PORT_HUB_V2 if hub_version == 2 else PORT_HUB_V1
    schema = {
        vol.Required(CONF_HOST, default=host): str,
        vol.Required(CONF_PORT, default=port): int,
        vol.Required(CONF_HUB_VERSION, default=hub_version): int,
    }
    if hub_version == 2:
        schema[vol.Required(CONF_USERNAME, default=username)] = str
        schema[vol.Required(CONF_PASSWORD, default=password)] = str
    return vol.Schema(schema)
