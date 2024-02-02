"""Validate Modbus configuration."""
from __future__ import annotations

from collections import namedtuple
import logging
import struct
from typing import Any

import voluptuous as vol

from homeassistant.const import (
    CONF_ADDRESS,
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_COUNT,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    CONF_STRUCTURE,
    CONF_TIMEOUT,
    CONF_TYPE,
)

from .const import (
    CONF_DATA_TYPE,
    CONF_DEVICE_ADDRESS,
    CONF_FAN_MODE_REGISTER,
    CONF_FAN_MODE_VALUES,
    CONF_HVAC_MODE_REGISTER,
    CONF_INPUT_TYPE,
    CONF_SLAVE_COUNT,
    CONF_SWAP,
    CONF_SWAP_BYTE,
    CONF_SWAP_WORD,
    CONF_SWAP_WORD_BYTE,
    CONF_TARGET_TEMP,
    CONF_VIRTUAL_COUNT,
    CONF_WRITE_TYPE,
    DEFAULT_HUB,
    DEFAULT_SCAN_INTERVAL,
    PLATFORMS,
    SERIAL,
    DataType,
)

_LOGGER = logging.getLogger(__name__)

ENTRY = namedtuple(
    "ENTRY",
    [
        "struct_id",
        "register_count",
        "validate_parm",
    ],
)


ILLEGAL = "I"
OPTIONAL = "O"
DEMANDED = "D"

PARM_IS_LEGAL = namedtuple(
    "PARM_IS_LEGAL",
    [
        "count",
        "structure",
        "slave_count",
        "swap_byte",
        "swap_word",
    ],
)
DEFAULT_STRUCT_FORMAT = {
    DataType.INT16: ENTRY(
        "h", 1, PARM_IS_LEGAL(ILLEGAL, ILLEGAL, OPTIONAL, OPTIONAL, ILLEGAL)
    ),
    DataType.UINT16: ENTRY(
        "H", 1, PARM_IS_LEGAL(ILLEGAL, ILLEGAL, OPTIONAL, OPTIONAL, ILLEGAL)
    ),
    DataType.FLOAT16: ENTRY(
        "e", 1, PARM_IS_LEGAL(ILLEGAL, ILLEGAL, OPTIONAL, OPTIONAL, ILLEGAL)
    ),
    DataType.INT32: ENTRY(
        "i", 2, PARM_IS_LEGAL(ILLEGAL, ILLEGAL, OPTIONAL, OPTIONAL, OPTIONAL)
    ),
    DataType.UINT32: ENTRY(
        "I", 2, PARM_IS_LEGAL(ILLEGAL, ILLEGAL, OPTIONAL, OPTIONAL, OPTIONAL)
    ),
    DataType.FLOAT32: ENTRY(
        "f", 2, PARM_IS_LEGAL(ILLEGAL, ILLEGAL, OPTIONAL, OPTIONAL, OPTIONAL)
    ),
    DataType.INT64: ENTRY(
        "q", 4, PARM_IS_LEGAL(ILLEGAL, ILLEGAL, OPTIONAL, OPTIONAL, OPTIONAL)
    ),
    DataType.UINT64: ENTRY(
        "Q", 4, PARM_IS_LEGAL(ILLEGAL, ILLEGAL, OPTIONAL, OPTIONAL, OPTIONAL)
    ),
    DataType.FLOAT64: ENTRY(
        "d", 4, PARM_IS_LEGAL(ILLEGAL, ILLEGAL, OPTIONAL, OPTIONAL, OPTIONAL)
    ),
    DataType.STRING: ENTRY(
        "s", 0, PARM_IS_LEGAL(DEMANDED, ILLEGAL, ILLEGAL, OPTIONAL, ILLEGAL)
    ),
    DataType.CUSTOM: ENTRY(
        "?", 0, PARM_IS_LEGAL(DEMANDED, DEMANDED, ILLEGAL, ILLEGAL, ILLEGAL)
    ),
}


def struct_validator(config: dict[str, Any]) -> dict[str, Any]:
    """Sensor schema validator."""

    name = config[CONF_NAME]
    data_type = config[CONF_DATA_TYPE]
    if data_type == "int":
        data_type = config[CONF_DATA_TYPE] = DataType.INT16
    count = config.get(CONF_COUNT, None)
    structure = config.get(CONF_STRUCTURE, None)
    slave_count = config.get(CONF_SLAVE_COUNT, config.get(CONF_VIRTUAL_COUNT))
    validator = DEFAULT_STRUCT_FORMAT[data_type].validate_parm
    swap_type = config.get(CONF_SWAP)
    swap_dict = {
        CONF_SWAP_BYTE: validator.swap_byte,
        CONF_SWAP_WORD: validator.swap_word,
        CONF_SWAP_WORD_BYTE: validator.swap_word,
    }
    swap_type_validator = swap_dict[swap_type] if swap_type else OPTIONAL
    for entry in (
        (count, validator.count, CONF_COUNT),
        (structure, validator.structure, CONF_STRUCTURE),
        (
            slave_count,
            validator.slave_count,
            f"{CONF_VIRTUAL_COUNT} / {CONF_SLAVE_COUNT}:",
        ),
        (swap_type, swap_type_validator, f"{CONF_SWAP}:{swap_type}"),
    ):
        if entry[0] is None:
            if entry[1] == DEMANDED:
                error = f"{name}: `{entry[2]}` missing, demanded with `{CONF_DATA_TYPE}: {data_type}`"
                raise vol.Invalid(error)
        elif entry[1] == ILLEGAL:
            error = f"{name}: `{entry[2]}` illegal with `{CONF_DATA_TYPE}: {data_type}`"
            raise vol.Invalid(error)

    if config[CONF_DATA_TYPE] == DataType.CUSTOM:
        try:
            size = struct.calcsize(structure)
        except struct.error as err:
            raise vol.Invalid(
                f"{name}: error in structure format --> {str(err)}"
            ) from err
        bytecount = count * 2
        if bytecount != size:
            raise vol.Invalid(
                f"{name}: Size of structure is {size} bytes but `{CONF_COUNT}: {count}` is {bytecount} bytes"
            )
    else:
        if data_type != DataType.STRING:
            config[CONF_COUNT] = DEFAULT_STRUCT_FORMAT[data_type].register_count
        if slave_count:
            structure = (
                f">{slave_count + 1}{DEFAULT_STRUCT_FORMAT[data_type].struct_id}"
            )
        else:
            structure = f">{DEFAULT_STRUCT_FORMAT[data_type].struct_id}"
    return {
        **config,
        CONF_STRUCTURE: structure,
        CONF_SWAP: swap_type,
    }


def nan_validator(value: Any) -> int:
    """Convert nan string to number (can be hex string or int)."""
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        pass
    try:
        return int(value, 16)
    except (TypeError, ValueError) as err:
        raise vol.Invalid(f"invalid number {value}") from err


def duplicate_fan_mode_validator(config: dict[str, Any]) -> dict:
    """Control modbus climate fan mode values for duplicates."""
    fan_modes: set[int] = set()
    errors = []
    for key, value in config[CONF_FAN_MODE_VALUES].items():
        if value in fan_modes:
            warn = f"Modbus fan mode {key} has a duplicate value {value}, not loaded, values must be unique!"
            _LOGGER.warning(warn)
            errors.append(key)
        else:
            fan_modes.add(value)

    for key in reversed(errors):
        del config[CONF_FAN_MODE_VALUES][key]
    return config


def register_int_list_validator(value: Any) -> Any:
    """Check if a register (CONF_ADRESS) is an int or a list having only 1 register."""
    if isinstance(value, int) and value >= 0:
        return value

    if isinstance(value, list):
        if (len(value) == 1) and isinstance(value[0], int) and value[0] >= 0:
            return value

    raise vol.Invalid(
        f"Invalid {CONF_ADDRESS} register for fan mode. Required type: positive integer, allowed 1 or list of 1 register."
    )


def check_config(config: dict) -> dict:
    """Do final config check."""
    hosts: set[str] = set()
    hub_names: set[str] = set()
    hub_name_inx = 0
    minimum_scan_interval = 0
    ent_names: set[str] = set()
    ent_addr: set[str] = set()

    def validate_modbus(hub: dict, hub_name_inx: int) -> bool:
        """Validate modbus entries."""
        host: str = (
            hub[CONF_PORT]
            if hub[CONF_TYPE] == SERIAL
            else f"{hub[CONF_HOST]}_{hub[CONF_PORT]}"
        )
        if CONF_NAME not in hub:
            hub[CONF_NAME] = (
                DEFAULT_HUB if not hub_name_inx else f"{DEFAULT_HUB}_{hub_name_inx}"
            )
            hub_name_inx += 1
            err = f"Modbus host/port {host} is missing name, added {hub[CONF_NAME]}!"
            _LOGGER.warning(err)
        name = hub[CONF_NAME]
        if host in hosts or name in hub_names:
            err = f"Modbus {name} host/port {host} is duplicate, not loaded!"
            _LOGGER.warning(err)
            return False
        hosts.add(host)
        hub_names.add(name)
        return True

    def validate_entity(
        hub_name: str,
        entity: dict,
        minimum_scan_interval: int,
        ent_names: set,
        ent_addr: set,
    ) -> bool:
        """Validate entity."""
        name = entity[CONF_NAME]
        addr = str(entity[CONF_ADDRESS])
        scan_interval = entity.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        if scan_interval < 5:
            _LOGGER.warning(
                (
                    "%s %s scan_interval(%d) is lower than 5 seconds, "
                    "which may cause Home Assistant stability issues"
                ),
                hub_name,
                name,
                scan_interval,
            )
        entity[CONF_SCAN_INTERVAL] = scan_interval
        minimum_scan_interval = min(scan_interval, minimum_scan_interval)
        for conf_type in (
            CONF_INPUT_TYPE,
            CONF_WRITE_TYPE,
            CONF_COMMAND_ON,
            CONF_COMMAND_OFF,
        ):
            if conf_type in entity:
                addr += f"_{entity[conf_type]}"
        inx = entity.get(CONF_SLAVE, None) or entity.get(CONF_DEVICE_ADDRESS, 0)
        addr += f"_{inx}"
        loc_addr: set[str] = {addr}

        if CONF_TARGET_TEMP in entity:
            loc_addr.add(f"{entity[CONF_TARGET_TEMP]}_{inx}")
        if CONF_HVAC_MODE_REGISTER in entity:
            loc_addr.add(f"{entity[CONF_HVAC_MODE_REGISTER][CONF_ADDRESS]}_{inx}")
        if CONF_FAN_MODE_REGISTER in entity:
            loc_addr.add(f"{entity[CONF_FAN_MODE_REGISTER][CONF_ADDRESS]}_{inx}")

        dup_addrs = ent_addr.intersection(loc_addr)
        if len(dup_addrs) > 0:
            for addr in dup_addrs:
                err = (
                    f"Modbus {hub_name}/{name} address {addr} is duplicate, second"
                    " entry not loaded!"
                )
                _LOGGER.warning(err)
            return False
        if name in ent_names:
            err = f"Modbus {hub_name}/{name} is duplicate, second entry not loaded!"
            _LOGGER.warning(err)
            return False
        ent_names.add(name)
        ent_addr.update(loc_addr)
        return True

    hub_inx = 0
    while hub_inx < len(config):
        hub = config[hub_inx]
        if not validate_modbus(hub, hub_name_inx):
            del config[hub_inx]
            continue
        for _component, conf_key in PLATFORMS:
            if conf_key not in hub:
                continue
            entity_inx = 0
            entities = hub[conf_key]
            minimum_scan_interval = 9999
            while entity_inx < len(entities):
                if not validate_entity(
                    hub[CONF_NAME],
                    entities[entity_inx],
                    minimum_scan_interval,
                    ent_names,
                    ent_addr,
                ):
                    del entities[entity_inx]
                else:
                    entity_inx += 1

        if hub[CONF_TIMEOUT] >= minimum_scan_interval:
            hub[CONF_TIMEOUT] = minimum_scan_interval - 1
            _LOGGER.warning(
                "Modbus %s timeout is adjusted(%d) due to scan_interval",
                hub[CONF_NAME],
                hub[CONF_TIMEOUT],
            )
        hub_inx += 1
    return config
