"""Helpers for LCN component."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from itertools import chain
import re
from typing import TypeAlias, cast

import pypck
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
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
    CONF_RESOURCE,
    CONF_SENSORS,
    CONF_SOURCE,
    CONF_SWITCHES,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .const import (
    BINSENSOR_PORTS,
    CONF_CLIMATES,
    CONF_CONNECTIONS,
    CONF_DIM_MODE,
    CONF_DOMAIN_DATA,
    CONF_HARDWARE_SERIAL,
    CONF_HARDWARE_TYPE,
    CONF_OUTPUT,
    CONF_SCENES,
    CONF_SK_NUM_TRIES,
    CONF_SOFTWARE_SERIAL,
    CONNECTION,
    DEFAULT_NAME,
    DOMAIN,
    LED_PORTS,
    LOGICOP_PORTS,
    OUTPUT_PORTS,
    S0_INPUTS,
    SETPOINTS,
    THRESHOLDS,
    VARIABLES,
)

# typing
AddressType = tuple[int, int, bool]
DeviceConnectionType: TypeAlias = (
    pypck.module.ModuleConnection | pypck.module.GroupConnection
)

InputType = type[pypck.inputs.Input]

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


def get_device_connection(
    hass: HomeAssistant, address: AddressType, config_entry: ConfigEntry
) -> DeviceConnectionType | None:
    """Return a lcn device_connection."""
    host_connection = hass.data[DOMAIN][config_entry.entry_id][CONNECTION]
    addr = pypck.lcn_addr.LcnAddr(*address)
    return host_connection.get_address_conn(addr)


def get_resource(domain_name: str, domain_data: ConfigType) -> str:
    """Return the resource for the specified domain_data."""
    if domain_name in ("switch", "light"):
        return cast(str, domain_data["output"])
    if domain_name in ("binary_sensor", "sensor"):
        return cast(str, domain_data["source"])
    if domain_name == "cover":
        return cast(str, domain_data["motor"])
    if domain_name == "climate":
        return f'{domain_data["source"]}.{domain_data["setpoint"]}'
    if domain_name == "scene":
        return f'{domain_data["register"]}.{domain_data["scene"]}'
    raise ValueError("Unknown domain")


def get_device_model(domain_name: str, domain_data: ConfigType) -> str:
    """Return the model for the specified domain_data."""
    if domain_name in ("switch", "light"):
        return "Output" if domain_data[CONF_OUTPUT] in OUTPUT_PORTS else "Relay"
    if domain_name in ("binary_sensor", "sensor"):
        if domain_data[CONF_SOURCE] in BINSENSOR_PORTS:
            return "Binary Sensor"
        if domain_data[CONF_SOURCE] in chain(
            VARIABLES, SETPOINTS, THRESHOLDS, S0_INPUTS
        ):
            return "Variable"
        if domain_data[CONF_SOURCE] in LED_PORTS:
            return "Led"
        if domain_data[CONF_SOURCE] in LOGICOP_PORTS:
            return "Logical Operation"
        return "Key"
    if domain_name == "cover":
        return "Motor"
    if domain_name == "climate":
        return "Regulator"
    if domain_name == "scene":
        return "Scene"
    raise ValueError("Unknown domain")


def generate_unique_id(
    entry_id: str,
    address: AddressType,
    resource: str | None = None,
) -> str:
    """Generate a unique_id from the given parameters."""
    unique_id = entry_id
    is_group = "g" if address[2] else "m"
    unique_id += f"-{is_group}{address[0]:03d}{address[1]:03d}"
    if resource:
        unique_id += f"-{resource}".lower()
    return unique_id


def import_lcn_config(lcn_config: ConfigType) -> list[ConfigType]:
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


def purge_entity_registry(
    hass: HomeAssistant, entry_id: str, imported_entry_data: ConfigType
) -> None:
    """Remove orphans from entity registry which are not in entry data."""
    entity_registry = er.async_get(hass)

    # Find all entities that are referenced in the config entry.
    references_config_entry = {
        entity_entry.entity_id
        for entity_entry in er.async_entries_for_config_entry(entity_registry, entry_id)
    }

    # Find all entities that are referenced by the entry_data.
    references_entry_data = set()
    for entity_data in imported_entry_data[CONF_ENTITIES]:
        entity_unique_id = generate_unique_id(
            entry_id, entity_data[CONF_ADDRESS], entity_data[CONF_RESOURCE]
        )
        entity_id = entity_registry.async_get_entity_id(
            entity_data[CONF_DOMAIN], DOMAIN, entity_unique_id
        )
        if entity_id is not None:
            references_entry_data.add(entity_id)

    orphaned_ids = references_config_entry - references_entry_data
    for orphaned_id in orphaned_ids:
        entity_registry.async_remove(orphaned_id)


def purge_device_registry(
    hass: HomeAssistant, entry_id: str, imported_entry_data: ConfigType
) -> None:
    """Remove orphans from device registry which are not in entry data."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    # Find all devices that are referenced in the entity registry.
    references_entities = {
        entry.device_id
        for entry in entity_registry.entities.get_entries_for_config_entry_id(entry_id)
    }

    # Find device that references the host.
    references_host = set()
    host_device = device_registry.async_get_device(identifiers={(DOMAIN, entry_id)})
    if host_device is not None:
        references_host.add(host_device.id)

    # Find all devices that are referenced by the entry_data.
    references_entry_data = set()
    for device_data in imported_entry_data[CONF_DEVICES]:
        device_unique_id = generate_unique_id(entry_id, device_data[CONF_ADDRESS])
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, device_unique_id)}
        )
        if device is not None:
            references_entry_data.add(device.id)

    orphaned_ids = (
        {
            entry.id
            for entry in dr.async_entries_for_config_entry(device_registry, entry_id)
        }
        - references_entities
        - references_host
        - references_entry_data
    )

    for device_id in orphaned_ids:
        device_registry.async_remove_device(device_id)


def register_lcn_host_device(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Register LCN host for given config_entry in device registry."""
    device_registry = dr.async_get(hass)

    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, config_entry.entry_id)},
        manufacturer="Issendorff",
        name=config_entry.title,
        model="LCN-PCHK",
    )


def register_lcn_address_devices(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Register LCN modules and groups defined in config_entry as devices in device registry.

    The name of all given device_connections is collected and the devices
    are updated.
    """
    device_registry = dr.async_get(hass)

    host_identifiers = (DOMAIN, config_entry.entry_id)

    for device_config in config_entry.data[CONF_DEVICES]:
        address = device_config[CONF_ADDRESS]
        device_name = device_config[CONF_NAME]
        identifiers = {(DOMAIN, generate_unique_id(config_entry.entry_id, address))}

        if device_config[CONF_ADDRESS][2]:  # is group
            device_model = f"LCN group (g{address[0]:03d}{address[1]:03d})"
            sw_version = None
        else:  # is module
            hardware_type = device_config[CONF_HARDWARE_TYPE]
            if hardware_type in pypck.lcn_defs.HARDWARE_DESCRIPTIONS:
                hardware_name = pypck.lcn_defs.HARDWARE_DESCRIPTIONS[hardware_type]
            else:
                hardware_name = pypck.lcn_defs.HARDWARE_DESCRIPTIONS[-1]
            device_model = f"{hardware_name} (m{address[0]:03d}{address[1]:03d})"
            sw_version = f"{device_config[CONF_SOFTWARE_SERIAL]:06X}"

        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers=identifiers,
            via_device=host_identifiers,
            manufacturer="Issendorff",
            sw_version=sw_version,
            name=device_name,
            model=device_model,
        )


async def async_update_device_config(
    device_connection: DeviceConnectionType, device_config: ConfigType
) -> None:
    """Fill missing values in device_config with infos from LCN bus."""
    # fetch serial info if device is module
    if not (is_group := device_config[CONF_ADDRESS][2]):  # is module
        await device_connection.serial_known
        if device_config[CONF_HARDWARE_SERIAL] == -1:
            device_config[CONF_HARDWARE_SERIAL] = device_connection.hardware_serial
        if device_config[CONF_SOFTWARE_SERIAL] == -1:
            device_config[CONF_SOFTWARE_SERIAL] = device_connection.software_serial
        if device_config[CONF_HARDWARE_TYPE] == -1:
            device_config[CONF_HARDWARE_TYPE] = device_connection.hardware_type.value

    # fetch name if device is module
    if device_config[CONF_NAME] != "":
        return

    device_name = ""
    if not is_group:
        device_name = await device_connection.request_name()
    if is_group or device_name == "":
        module_type = "Group" if is_group else "Module"
        device_name = (
            f"{module_type} "
            f"{device_config[CONF_ADDRESS][0]:03d}/"
            f"{device_config[CONF_ADDRESS][1]:03d}"
        )
    device_config[CONF_NAME] = device_name


async def async_update_config_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Fill missing values in config_entry with infos from LCN bus."""
    device_configs = deepcopy(config_entry.data[CONF_DEVICES])
    coros = []
    for device_config in device_configs:
        device_connection = get_device_connection(
            hass, device_config[CONF_ADDRESS], config_entry
        )
        coros.append(async_update_device_config(device_connection, device_config))

    await asyncio.gather(*coros)

    new_data = {**config_entry.data, CONF_DEVICES: device_configs}

    # schedule config_entry for save
    hass.config_entries.async_update_entry(config_entry, data=new_data)


def has_unique_host_names(hosts: list[ConfigType]) -> list[ConfigType]:
    """Validate that all connection names are unique.

    Use 'pchk' as default connection_name (or add a numeric suffix if
    pchk' is already in use.
    """
    suffix = 0
    for host in hosts:
        if host.get(CONF_NAME) is None:
            if suffix == 0:
                host[CONF_NAME] = DEFAULT_NAME
            else:
                host[CONF_NAME] = f"{DEFAULT_NAME}{suffix:d}"
            suffix += 1

    schema = vol.Schema(vol.Unique())
    schema([host.get(CONF_NAME) for host in hosts])
    return hosts


def is_address(value: str) -> tuple[AddressType, str]:
    """Validate the given address string.

    Examples for S000M005 at myhome:
        myhome.s000.m005
        myhome.s0.m5
        myhome.0.5    ("m" is implicit if missing)

    Examples for s000g011
        myhome.0.g11
        myhome.s0.g11
    """
    if matcher := PATTERN_ADDRESS.match(value):
        is_group = matcher.group("type") == "g"
        addr = (int(matcher.group("seg_id")), int(matcher.group("id")), is_group)
        conn_id = matcher.group("conn_id")
        return addr, conn_id
    raise ValueError(f"{value} is not a valid address string")


def is_states_string(states_string: str) -> list[str]:
    """Validate the given states string and return states list."""
    if len(states_string) != 8:
        raise ValueError("Invalid length of states string")
    states = {"1": "ON", "0": "OFF", "T": "TOGGLE", "-": "NOCHANGE"}
    return [states[state_string] for state_string in states_string]
