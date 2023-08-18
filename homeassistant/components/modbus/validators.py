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
    CONF_INPUT_TYPE,
    CONF_SLAVE_COUNT,
    CONF_SWAP,
    CONF_SWAP_BYTE,
    CONF_SWAP_NONE,
    CONF_WRITE_TYPE,
    DEFAULT_HUB,
    DEFAULT_SCAN_INTERVAL,
    PLATFORMS,
    SERIAL,
    DataType,
)

_LOGGER = logging.getLogger(__name__)

ENTRY = namedtuple("ENTRY", ["struct_id", "register_count"])
DEFAULT_STRUCT_FORMAT = {
    DataType.INT8: ENTRY("b", 1),
    DataType.INT16: ENTRY("h", 1),
    DataType.INT32: ENTRY("i", 2),
    DataType.INT64: ENTRY("q", 4),
    DataType.UINT8: ENTRY("c", 1),
    DataType.UINT16: ENTRY("H", 1),
    DataType.UINT32: ENTRY("I", 2),
    DataType.UINT64: ENTRY("Q", 4),
    DataType.FLOAT16: ENTRY("e", 1),
    DataType.FLOAT32: ENTRY("f", 2),
    DataType.FLOAT64: ENTRY("d", 4),
    DataType.STRING: ENTRY("s", 1),
}


def struct_validator(config: dict[str, Any]) -> dict[str, Any]:
    """Sensor schema validator."""

    data_type = config[CONF_DATA_TYPE]
    count = config.get(CONF_COUNT, 1)
    name = config[CONF_NAME]
    structure = config.get(CONF_STRUCTURE)
    slave_count = config.get(CONF_SLAVE_COUNT, 0) + 1
    swap_type = config.get(CONF_SWAP, CONF_SWAP_NONE)
    if (
        slave_count > 1
        and count > 1
        and data_type not in (DataType.CUSTOM, DataType.STRING)
    ):
        error = f"{name}  {CONF_COUNT} cannot be mixed with {data_type}"
        raise vol.Invalid(error)
    if config[CONF_DATA_TYPE] != DataType.CUSTOM:
        if structure:
            error = f"{name}  structure: cannot be mixed with {data_type}"

    if config[CONF_DATA_TYPE] == DataType.CUSTOM:
        if slave_count > 1:
            error = f"{name}: `{CONF_STRUCTURE}` illegal with `{CONF_SLAVE_COUNT}` / `{CONF_SLAVE}`"
            raise vol.Invalid(error)
        if swap_type != CONF_SWAP_NONE:
            error = f"{name}: `{CONF_STRUCTURE}` illegal with `{CONF_SWAP}`"
            raise vol.Invalid(error)
        if not structure:
            error = (
                f"Error in sensor {name}. The `{CONF_STRUCTURE}` field cannot be empty"
            )
            raise vol.Invalid(error)
        try:
            size = struct.calcsize(structure)
        except struct.error as err:
            raise vol.Invalid(f"Error in {name} structure: {str(err)}") from err

        count = config.get(CONF_COUNT, 1)
        bytecount = count * 2
        if bytecount != size:
            raise vol.Invalid(
                f"Structure request {size} bytes, "
                f"but {count} registers have a size of {bytecount} bytes"
            )
        return {
            **config,
            CONF_STRUCTURE: structure,
            CONF_SWAP: swap_type,
        }
    if data_type not in DEFAULT_STRUCT_FORMAT:
        error = f"Error in sensor {name}. data_type `{data_type}` not supported"
        raise vol.Invalid(error)
    if slave_count > 1 and data_type == DataType.STRING:
        error = f"{name}: `{data_type}`  illegal with `{CONF_SLAVE_COUNT}`"
        raise vol.Invalid(error)

    if CONF_COUNT not in config:
        config[CONF_COUNT] = DEFAULT_STRUCT_FORMAT[data_type].register_count
    if swap_type != CONF_SWAP_NONE:
        if swap_type == CONF_SWAP_BYTE:
            regs_needed = 1
        else:  # CONF_SWAP_WORD_BYTE, CONF_SWAP_WORD
            regs_needed = 2
        count = config[CONF_COUNT]
        if count < regs_needed or (count % regs_needed) != 0:
            raise vol.Invalid(
                f"Error in sensor {name} swap({swap_type}) "
                "not possible due to the registers "
                f"count: {count}, needed: {regs_needed}"
            )
    structure = f">{DEFAULT_STRUCT_FORMAT[data_type].struct_id}"
    if slave_count > 1:
        structure = f">{slave_count}{DEFAULT_STRUCT_FORMAT[data_type].struct_id}"
    else:
        structure = f">{DEFAULT_STRUCT_FORMAT[data_type].struct_id}"
    return {
        **config,
        CONF_STRUCTURE: structure,
        CONF_SWAP: swap_type,
    }


def number_validator(value: Any) -> int | float:
    """Coerce a value to number without losing precision."""
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value

    try:
        return int(value)
    except (TypeError, ValueError):
        pass
    try:
        return float(value)
    except (TypeError, ValueError) as err:
        raise vol.Invalid(f"invalid number {value}") from err


def scan_interval_validator(config: dict) -> dict:
    """Control scan_interval."""
    for hub in config:
        minimum_scan_interval = DEFAULT_SCAN_INTERVAL
        for component, conf_key in PLATFORMS:
            if conf_key not in hub:
                continue

            for entry in hub[conf_key]:
                scan_interval = entry.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                if scan_interval == 0:
                    continue
                if scan_interval < 5:
                    _LOGGER.warning(
                        (
                            "%s %s scan_interval(%d) is lower than 5 seconds, "
                            "which may cause Home Assistant stability issues"
                        ),
                        component,
                        entry.get(CONF_NAME),
                        scan_interval,
                    )
                entry[CONF_SCAN_INTERVAL] = scan_interval
                minimum_scan_interval = min(scan_interval, minimum_scan_interval)
        if (
            CONF_TIMEOUT in hub
            and hub[CONF_TIMEOUT] > minimum_scan_interval - 1
            and minimum_scan_interval > 1
        ):
            _LOGGER.warning(
                "Modbus %s timeout(%d) is adjusted(%d) due to scan_interval",
                hub.get(CONF_NAME, ""),
                hub[CONF_TIMEOUT],
                minimum_scan_interval - 1,
            )
            hub[CONF_TIMEOUT] = minimum_scan_interval - 1
    return config


def duplicate_entity_validator(config: dict) -> dict:
    """Control scan_interval."""
    for hub_index, hub in enumerate(config):
        for component, conf_key in PLATFORMS:
            if conf_key not in hub:
                continue
            names: set[str] = set()
            errors: list[int] = []
            addresses: set[str] = set()
            for index, entry in enumerate(hub[conf_key]):
                name = entry[CONF_NAME]
                addr = str(entry[CONF_ADDRESS])
                if CONF_INPUT_TYPE in entry:
                    addr += "_" + str(entry[CONF_INPUT_TYPE])
                elif CONF_WRITE_TYPE in entry:
                    addr += "_" + str(entry[CONF_WRITE_TYPE])
                if CONF_COMMAND_ON in entry:
                    addr += "_" + str(entry[CONF_COMMAND_ON])
                if CONF_COMMAND_OFF in entry:
                    addr += "_" + str(entry[CONF_COMMAND_OFF])
                addr += "_" + str(entry.get(CONF_SLAVE, 0))
                if addr in addresses:
                    err = (
                        f"Modbus {component}/{name} address {addr} is duplicate, second"
                        " entry not loaded!"
                    )
                    _LOGGER.warning(err)
                    errors.append(index)
                elif name in names:
                    err = (
                        f"Modbus {component}/{name}  is duplicate, second entry not"
                        " loaded!"
                    )
                    _LOGGER.warning(err)
                    errors.append(index)
                else:
                    names.add(name)
                    addresses.add(addr)

            for i in reversed(errors):
                del config[hub_index][conf_key][i]
    return config


def duplicate_modbus_validator(config: list) -> list:
    """Control modbus connection for duplicates."""
    hosts: set[str] = set()
    names: set[str] = set()
    errors = []
    for index, hub in enumerate(config):
        name = hub.get(CONF_NAME, DEFAULT_HUB)
        if hub[CONF_TYPE] == SERIAL:
            host = hub[CONF_PORT]
        else:
            host = f"{hub[CONF_HOST]}_{hub[CONF_PORT]}"
        if host in hosts:
            err = f"Modbus {name}  contains duplicate host/port {host}, not loaded!"
            _LOGGER.warning(err)
            errors.append(index)
        elif name in names:
            err = f"Modbus {name}  is duplicate, second entry not loaded!"
            _LOGGER.warning(err)
            errors.append(index)
        else:
            hosts.add(host)
            names.add(name)

    for i in reversed(errors):
        del config[i]
    return config
