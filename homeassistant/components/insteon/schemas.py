"""Schemas used by insteon component."""

import probatio
from pyinsteon.constants import HC_LOOKUP

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

ADD_ALL_LINK_SCHEMA = probatio.Schema(
    {
        probatio.Required(SRV_ALL_LINK_GROUP): probatio.Range(min=0, max=255),
        probatio.Required(SRV_ALL_LINK_MODE): probatio.In(
            [SRV_CONTROLLER, SRV_RESPONDER]
        ),
    }
)


DEL_ALL_LINK_SCHEMA = probatio.Schema(
    {probatio.Required(SRV_ALL_LINK_GROUP): probatio.Range(min=0, max=255)}
)


LOAD_ALDB_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_ENTITY_ID): probatio.Any(cv.entity_id, ENTITY_MATCH_ALL),
        probatio.Optional(SRV_LOAD_DB_RELOAD, default=False): cv.boolean,
    }
)


PRINT_ALDB_SCHEMA = probatio.Schema({probatio.Required(CONF_ENTITY_ID): cv.entity_id})


X10_HOUSECODE_SCHEMA = probatio.Schema(
    {probatio.Required(SRV_HOUSECODE): probatio.In(HOUSECODES)}
)


TRIGGER_SCENE_SCHEMA = probatio.Schema(
    {probatio.Required(SRV_ALL_LINK_GROUP): probatio.Range(min=0, max=255)}
)


ADD_DEFAULT_LINKS_SCHEMA = probatio.Schema(
    {probatio.Required(CONF_ENTITY_ID): cv.entity_id}
)


def build_device_override_schema(
    address=probatio.UNDEFINED,
    cat=probatio.UNDEFINED,
    subcat=probatio.UNDEFINED,
    firmware=probatio.UNDEFINED,
):
    """Build the device override schema for config flow."""
    return probatio.Schema(
        {
            probatio.Required(CONF_ADDRESS, default=address): str,
            probatio.Optional(CONF_CAT, default=cat): str,
            probatio.Optional(CONF_SUBCAT, default=subcat): str,
        }
    )


def build_x10_schema(
    housecode=probatio.UNDEFINED,
    unitcode=probatio.UNDEFINED,
    platform=probatio.UNDEFINED,
    dim_steps=22,
):
    """Build the X10 schema for config flow."""
    if platform == "light":
        dim_steps_schema = probatio.Required(CONF_DIM_STEPS, default=dim_steps)
    else:
        dim_steps_schema = probatio.Optional(CONF_DIM_STEPS, default=dim_steps)
    return probatio.Schema(
        {
            probatio.Required(CONF_HOUSECODE, default=housecode): probatio.In(
                HC_LOOKUP.keys()
            ),
            probatio.Required(CONF_UNITCODE, default=unitcode): probatio.In(
                range(1, 17)
            ),
            probatio.Required(CONF_PLATFORM, default=platform): probatio.In(
                X10_PLATFORMS
            ),
            dim_steps_schema: probatio.Range(min=0, max=255),
        }
    )


def _find_likely_port(ports):
    """Return the most likely USB port for a PLM."""
    test_strings = ["FTDI", "0403:6001", "10BF:"]
    for port, name in ports.items():
        for test_string in test_strings:
            if test_string in name:
                return port
    return probatio.UNDEFINED


def build_plm_schema(ports: dict[str, str], device=probatio.UNDEFINED):
    """Build the PLM schema for config flow."""
    if not device or device == probatio.UNDEFINED:
        device = _find_likely_port(ports)
    return probatio.Schema(
        {probatio.Required(CONF_DEVICE, default=device): probatio.In(ports)}
    )


def build_plm_manual_schema(device=probatio.UNDEFINED):
    """Build the manual PLM schema for config flow."""
    return probatio.Schema({probatio.Required(CONF_DEVICE, default=device): str})


def build_hub_schema(
    hub_version,
    host=probatio.UNDEFINED,
    port=probatio.UNDEFINED,
    username=probatio.UNDEFINED,
    password=probatio.UNDEFINED,
):
    """Build the Hub schema for config flow."""
    if port == probatio.UNDEFINED:
        port = PORT_HUB_V2 if hub_version == 2 else PORT_HUB_V1
    schema = {
        probatio.Required(CONF_HOST, default=host): str,
        probatio.Required(CONF_PORT, default=port): int,
        probatio.Required(CONF_HUB_VERSION, default=hub_version): int,
    }
    if hub_version == 2:
        schema[probatio.Required(CONF_USERNAME, default=username)] = str
        schema[probatio.Required(CONF_PASSWORD, default=password)] = str
    return probatio.Schema(schema)
