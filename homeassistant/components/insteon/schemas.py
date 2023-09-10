"""Schemas used by insteon component."""
from __future__ import annotations

from binascii import Error as HexError, unhexlify

from pyinsteon.address import Address
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
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_CAT,
    CONF_DIM_STEPS,
    CONF_HOUSECODE,
    CONF_OVERRIDE,
    CONF_SUBCAT,
    CONF_UNITCODE,
    CONF_X10,
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


def normalize_byte_entry_to_int(entry: int | bytes | str):
    """Format a hex entry value."""
    if isinstance(entry, int):
        if entry in range(0, 256):
            return entry
        raise ValueError("Must be single byte")
    if isinstance(entry, str):
        if entry[0:2].lower() == "0x":
            entry = entry[2:]
        if len(entry) != 2:
            raise ValueError("Not a valid hex code")
        try:
            entry = unhexlify(entry)
        except HexError as err:
            raise ValueError("Not a valid hex code") from err
    return int.from_bytes(entry, byteorder="big")


def add_device_override(config_data, new_override):
    """Add a new device override."""
    try:
        address = str(Address(new_override[CONF_ADDRESS]))
        cat = normalize_byte_entry_to_int(new_override[CONF_CAT])
        subcat = normalize_byte_entry_to_int(new_override[CONF_SUBCAT])
    except ValueError as err:
        raise ValueError("Incorrect values") from err

    overrides = []

    for override in config_data.get(CONF_OVERRIDE, []):
        if override[CONF_ADDRESS] != address:
            overrides.append(override)

    curr_override = {}
    curr_override[CONF_ADDRESS] = address
    curr_override[CONF_CAT] = cat
    curr_override[CONF_SUBCAT] = subcat
    overrides.append(curr_override)

    new_config = {}
    if config_data.get(CONF_X10):
        new_config[CONF_X10] = config_data[CONF_X10]
    new_config[CONF_OVERRIDE] = overrides
    return new_config


def add_x10_device(config_data, new_x10):
    """Add a new X10 device to X10 device list."""
    x10_devices = []
    for x10_device in config_data.get(CONF_X10, []):
        if (
            x10_device[CONF_HOUSECODE] != new_x10[CONF_HOUSECODE]
            or x10_device[CONF_UNITCODE] != new_x10[CONF_UNITCODE]
        ):
            x10_devices.append(x10_device)

    curr_device = {}
    curr_device[CONF_HOUSECODE] = new_x10[CONF_HOUSECODE]
    curr_device[CONF_UNITCODE] = new_x10[CONF_UNITCODE]
    curr_device[CONF_PLATFORM] = new_x10[CONF_PLATFORM]
    curr_device[CONF_DIM_STEPS] = new_x10[CONF_DIM_STEPS]
    x10_devices.append(curr_device)

    new_config = {}
    if config_data.get(CONF_OVERRIDE):
        new_config[CONF_OVERRIDE] = config_data[CONF_OVERRIDE]
    new_config[CONF_X10] = x10_devices
    return new_config


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
    return vol.Schema(
        {
            vol.Required(CONF_HOUSECODE, default=housecode): vol.In(HC_LOOKUP.keys()),
            vol.Required(CONF_UNITCODE, default=unitcode): vol.In(range(1, 17)),
            vol.Required(CONF_PLATFORM, default=platform): vol.In(X10_PLATFORMS),
            vol.Optional(CONF_DIM_STEPS, default=dim_steps): vol.In(range(1, 255)),
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
    }
    if hub_version == 2:
        schema[vol.Required(CONF_USERNAME, default=username)] = str
        schema[vol.Required(CONF_PASSWORD, default=password)] = str
    return vol.Schema(schema)


def build_remove_override_schema(data):
    """Build the schema to remove device overrides in config flow options."""
    selection = []
    for override in data:
        selection.append(override[CONF_ADDRESS])
    return vol.Schema({vol.Required(CONF_ADDRESS): vol.In(selection)})


def build_remove_x10_schema(data):
    """Build the schema to remove an X10 device in config flow options."""
    selection = []
    for device in data:
        housecode = device[CONF_HOUSECODE].upper()
        unitcode = device[CONF_UNITCODE]
        selection.append(f"Housecode: {housecode}, Unitcode: {unitcode}")
    return vol.Schema({vol.Required(CONF_DEVICE): vol.In(selection)})
