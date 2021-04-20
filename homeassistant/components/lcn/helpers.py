"""Helpers for LCN component."""
import re

import pypck
import voluptuous as vol

from homeassistant.const import (
    CONF_ADDRESS,
    CONF_BINARY_SENSORS,
    CONF_COVERS,
    CONF_DEVICES,
    CONF_DOMAIN,
    CONF_ENTITIES,
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_LIGHTS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SENSORS,
    CONF_SWITCHES,
    CONF_USERNAME,
)

from .const import (
    CONF_CLIMATES,
    CONF_CONNECTIONS,
    CONF_DIM_MODE,
    CONF_DOMAIN_DATA,
    CONF_HARDWARE_SERIAL,
    CONF_HARDWARE_TYPE,
    CONF_RESOURCE,
    CONF_SCENES,
    CONF_SK_NUM_TRIES,
    CONF_SOFTWARE_SERIAL,
    CONNECTION,
    DEFAULT_NAME,
    DOMAIN,
)

# Regex for address validation
PATTERN_ADDRESS = re.compile(
    "^((?P<conn_id>\\w+)\\.)?s?(?P<seg_id>\\d+)\\.(?P<type>m|g)?(?P<id>\\d+)$"
)


DOMAIN_LOOKUP = {
    CONF_BINARY_SENSORS: "binary_sensor",
    CONF_CLIMATES: "climate",
    CONF_COVERS: "cover",
    CONF_LIGHTS: "light",
    CONF_SCENES: "scene",
    CONF_SENSORS: "sensor",
    CONF_SWITCHES: "switch",
}


def get_device_connection(hass, address, config_entry):
    """Return a lcn device_connection."""
    host_connection = hass.data[DOMAIN][config_entry.entry_id][CONNECTION]
    addr = pypck.lcn_addr.LcnAddr(*address)
    return host_connection.get_address_conn(addr)


def get_resource(domain_name, domain_data):
    """Return the resource for the specified domain_data."""
    if domain_name in ["switch", "light"]:
        return domain_data["output"]
    if domain_name in ["binary_sensor", "sensor"]:
        return domain_data["source"]
    if domain_name == "cover":
        return domain_data["motor"]
    if domain_name == "climate":
        return f'{domain_data["source"]}.{domain_data["setpoint"]}'
    if domain_name == "scene":
        return f'{domain_data["register"]}.{domain_data["scene"]}'
    raise ValueError("Unknown domain")


def generate_unique_id(address):
    """Generate a unique_id from the given parameters."""
    is_group = "g" if address[2] else "m"
    return f"{is_group}{address[0]:03d}{address[1]:03d}"


def import_lcn_config(lcn_config):
    """Convert lcn settings from configuration.yaml to config_entries data.

    Create a list of config_entry data structures like:

    "data": {
        "host": "pchk",
        "ip_address": "192.168.2.41",
        "port": 4114,
        "username": "lcn",
        "password": "lcn,
        "sk_num_tries: 0,
        "dim_mode: "STEPS200",
        "devices": [
            {
                "address": (0, 7, False)
                "name": "",
                "hardware_serial": -1,
                "software_serial": -1,
                "hardware_type": -1
            }, ...
        ],
        "entities": [
            {
                "address": (0, 7, False)
                "name": "Light_Output1",
                "resource": "output1",
                "domain": "light",
                "domain_data": {
                    "output": "OUTPUT1",
                    "dimmable": True,
                    "transition": 5000.0
                }
            }, ...
        ]
    }
    """
    data = {}
    for connection in lcn_config[CONF_CONNECTIONS]:
        host = {
            CONF_HOST: connection[CONF_NAME],
            CONF_IP_ADDRESS: connection[CONF_HOST],
            CONF_PORT: connection[CONF_PORT],
            CONF_USERNAME: connection[CONF_USERNAME],
            CONF_PASSWORD: connection[CONF_PASSWORD],
            CONF_SK_NUM_TRIES: connection[CONF_SK_NUM_TRIES],
            CONF_DIM_MODE: connection[CONF_DIM_MODE],
            CONF_DEVICES: [],
            CONF_ENTITIES: [],
        }
        data[connection[CONF_NAME]] = host

    for confkey, domain_config in lcn_config.items():
        if confkey == CONF_CONNECTIONS:
            continue
        domain = DOMAIN_LOOKUP[confkey]
        # loop over entities in configuration.yaml
        for domain_data in domain_config:
            # remove name and address from domain_data
            entity_name = domain_data.pop(CONF_NAME)
            address, host_name = domain_data.pop(CONF_ADDRESS)

            if host_name is None:
                host_name = DEFAULT_NAME

            # check if we have a new device config
            for device_config in data[host_name][CONF_DEVICES]:
                if address == device_config[CONF_ADDRESS]:
                    break
            else:  # create new device_config
                device_config = {
                    CONF_ADDRESS: address,
                    CONF_NAME: "",
                    CONF_HARDWARE_SERIAL: -1,
                    CONF_SOFTWARE_SERIAL: -1,
                    CONF_HARDWARE_TYPE: -1,
                }

                data[host_name][CONF_DEVICES].append(device_config)

            # insert entity config
            resource = get_resource(domain, domain_data).lower()
            for entity_config in data[host_name][CONF_ENTITIES]:
                if (
                    address == entity_config[CONF_ADDRESS]
                    and resource == entity_config[CONF_RESOURCE]
                    and domain == entity_config[CONF_DOMAIN]
                ):
                    break
            else:  # create new entity_config
                entity_config = {
                    CONF_ADDRESS: address,
                    CONF_NAME: entity_name,
                    CONF_RESOURCE: resource,
                    CONF_DOMAIN: domain,
                    CONF_DOMAIN_DATA: domain_data.copy(),
                }
                data[host_name][CONF_ENTITIES].append(entity_config)

    return list(data.values())


def has_unique_host_names(hosts):
    """Validate that all connection names are unique.

    Use 'pchk' as default connection_name (or add a numeric suffix if
    pchk' is already in use.
    """
    suffix = 0
    for host in hosts:
        host_name = host.get(CONF_NAME)
        if host_name is None:
            if suffix == 0:
                host[CONF_NAME] = DEFAULT_NAME
            else:
                host[CONF_NAME] = f"{DEFAULT_NAME}{suffix:d}"
            suffix += 1

    schema = vol.Schema(vol.Unique())
    schema([host.get(CONF_NAME) for host in hosts])
    return hosts


def is_address(value):
    """Validate the given address string.

    Examples for S000M005 at myhome:
        myhome.s000.m005
        myhome.s0.m5
        myhome.0.5    ("m" is implicit if missing)

    Examples for s000g011
        myhome.0.g11
        myhome.s0.g11
    """
    matcher = PATTERN_ADDRESS.match(value)
    if matcher:
        is_group = matcher.group("type") == "g"
        addr = (int(matcher.group("seg_id")), int(matcher.group("id")), is_group)
        conn_id = matcher.group("conn_id")
        return addr, conn_id
    raise vol.error.Invalid("Not a valid address string.")


def is_relays_states_string(states_string):
    """Validate the given states string and return states list."""
    if len(states_string) == 8:
        states = []
        for state_string in states_string:
            if state_string == "1":
                state = "ON"
            elif state_string == "0":
                state = "OFF"
            elif state_string == "T":
                state = "TOGGLE"
            elif state_string == "-":
                state = "NOCHANGE"
            else:
                raise vol.error.Invalid("Not a valid relay state string.")
            states.append(state)
        return states
    raise vol.error.Invalid("Wrong length of relay state string.")


def is_key_lock_states_string(states_string):
    """Validate the given states string and returns states list."""
    if len(states_string) == 8:
        states = []
        for state_string in states_string:
            if state_string == "1":
                state = "ON"
            elif state_string == "0":
                state = "OFF"
            elif state_string == "T":
                state = "TOGGLE"
            elif state_string == "-":
                state = "NOCHANGE"
            else:
                raise vol.error.Invalid("Not a valid key lock state string.")
            states.append(state)
        return states
    raise vol.error.Invalid("Wrong length of key lock state string.")
