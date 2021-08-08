"""Validate Modbus configuration."""
from __future__ import annotations

import logging
import struct
from typing import Any

import voluptuous as vol

from homeassistant.const import (
    CONF_COUNT,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_STRUCTURE,
    CONF_TIMEOUT,
)

from .const import (
    CONF_DATA_TYPE,
    CONF_SWAP,
    CONF_SWAP_BYTE,
    CONF_SWAP_NONE,
    DATA_TYPE_CUSTOM,
    DATA_TYPE_FLOAT,
    DATA_TYPE_FLOAT16,
    DATA_TYPE_FLOAT32,
    DATA_TYPE_FLOAT64,
    DATA_TYPE_INT,
    DATA_TYPE_INT16,
    DATA_TYPE_INT32,
    DATA_TYPE_INT64,
    DATA_TYPE_UINT,
    DATA_TYPE_UINT16,
    DATA_TYPE_UINT32,
    DATA_TYPE_UINT64,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STRUCT_FORMAT,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)

OLD_DATA_TYPES = {
    DATA_TYPE_INT: {
        1: DATA_TYPE_INT16,
        2: DATA_TYPE_INT32,
        4: DATA_TYPE_INT64,
    },
    DATA_TYPE_UINT: {
        1: DATA_TYPE_UINT16,
        2: DATA_TYPE_UINT32,
        4: DATA_TYPE_UINT64,
    },
    DATA_TYPE_FLOAT: {
        1: DATA_TYPE_FLOAT16,
        2: DATA_TYPE_FLOAT32,
        4: DATA_TYPE_FLOAT64,
    },
}


def struct_validator(config):
    """Sensor schema validator."""

    data_type = config[CONF_DATA_TYPE]
    count = config.get(CONF_COUNT, 1)
    name = config[CONF_NAME]
    structure = config.get(CONF_STRUCTURE)
    swap_type = config.get(CONF_SWAP)
    if data_type in [DATA_TYPE_INT, DATA_TYPE_UINT, DATA_TYPE_FLOAT]:
        error = f"{name}  with {data_type} is not valid, trying to convert"
        _LOGGER.warning(error)
        try:
            data_type = OLD_DATA_TYPES[data_type][config.get(CONF_COUNT, 1)]
            config[CONF_DATA_TYPE] = data_type
        except KeyError as exp:
            error = f"{name}  cannot convert automatically {data_type}"
            raise vol.Invalid(error) from exp
    if config[CONF_DATA_TYPE] != DATA_TYPE_CUSTOM:
        if structure:
            error = f"{name}  structure: cannot be mixed with {data_type}"
            raise vol.Invalid(error)
        structure = f">{DEFAULT_STRUCT_FORMAT[data_type][0]}"
        if CONF_COUNT not in config:
            config[CONF_COUNT] = DEFAULT_STRUCT_FORMAT[data_type][1]
    else:
        if not structure:
            error = (
                f"Error in sensor {name}. The `{CONF_STRUCTURE}` field can not be empty"
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

        if swap_type != CONF_SWAP_NONE:
            if swap_type == CONF_SWAP_BYTE:
                regs_needed = 1
            else:  # CONF_SWAP_WORD_BYTE, CONF_SWAP_WORD
                regs_needed = 2
            if count < regs_needed or (count % regs_needed) != 0:
                raise vol.Invalid(
                    f"Error in sensor {name} swap({swap_type}) "
                    f"not possible due to the registers "
                    f"count: {count}, needed: {regs_needed}"
                )

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
        value = int(value)
        return value
    except (TypeError, ValueError):
        pass
    try:
        value = float(value)
        return value
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
                        "%s %s scan_interval(%d) is lower than 5 seconds, "
                        "which may cause Home Assistant stability issues",
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
