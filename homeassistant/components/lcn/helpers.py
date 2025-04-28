"""Helpers for LCN component."""

from __future__ import annotations

import asyncio
from copy import deepcopy
import re
from typing import cast

import pypck

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_BINARY_SENSORS,
    CONF_COVERS,
    CONF_DEVICES,
    CONF_DOMAIN,
    CONF_ENTITIES,
    CONF_LIGHTS,
    CONF_NAME,
    CONF_SENSORS,
    CONF_SWITCHES,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_CLIMATES,
    CONF_DOMAIN_DATA,
    CONF_HARDWARE_SERIAL,
    CONF_HARDWARE_TYPE,
    CONF_SCENES,
    CONF_SOFTWARE_SERIAL,
    CONNECTION,
    DEVICE_CONNECTIONS,
    DOMAIN,
)

# typing
type AddressType = tuple[int, int, bool]
type DeviceConnectionType = pypck.module.ModuleConnection | pypck.module.GroupConnection

type InputType = type[pypck.inputs.Input]

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
) -> DeviceConnectionType:
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
        return cast(str, domain_data["setpoint"])
    if domain_name == "scene":
        return f"{domain_data['register']}{domain_data['scene']}"
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
            entry_id,
            entity_data[CONF_ADDRESS],
            get_resource(entity_data[CONF_DOMAIN], entity_data[CONF_DOMAIN_DATA]),
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
            device_model = "LCN group"
            sw_version = None
        else:  # is module
            hardware_type = device_config[CONF_HARDWARE_TYPE]
            if hardware_type in pypck.lcn_defs.HARDWARE_DESCRIPTIONS:
                hardware_name = pypck.lcn_defs.HARDWARE_DESCRIPTIONS[hardware_type]
            else:
                hardware_name = pypck.lcn_defs.HARDWARE_DESCRIPTIONS[-1]
            device_model = f"{hardware_name}"
            sw_version = f"{device_config[CONF_SOFTWARE_SERIAL]:06X}"

        device_entry = device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers=identifiers,
            via_device=host_identifiers,
            manufacturer="Issendorff",
            sw_version=sw_version,
            name=device_name,
            model=device_model,
        )

        hass.data[DOMAIN][config_entry.entry_id][DEVICE_CONNECTIONS][
            device_entry.id
        ] = get_device_connection(hass, address, config_entry)


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


def get_device_config(
    address: AddressType, config_entry: ConfigEntry
) -> ConfigType | None:
    """Return the device configuration for given address and ConfigEntry."""
    for device_config in config_entry.data[CONF_DEVICES]:
        if tuple(device_config[CONF_ADDRESS]) == address:
            return cast(ConfigType, device_config)
    return None


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
