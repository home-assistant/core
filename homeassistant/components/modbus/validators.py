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
    DATA_TYPE_STRING,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STRUCT_FORMAT,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)


def sensor_schema_validator(config):
    """Sensor schema validator."""

    if config[CONF_DATA_TYPE] == DATA_TYPE_STRING:
        structure = str(config[CONF_COUNT] * 2) + "s"
    elif config[CONF_DATA_TYPE] != DATA_TYPE_CUSTOM:
        try:
            structure = (
                f">{DEFAULT_STRUCT_FORMAT[config[CONF_DATA_TYPE]][config[CONF_COUNT]]}"
            )
        except KeyError as key:
            raise vol.Invalid(
                f"Unable to detect data type for {config[CONF_NAME]} sensor, try a custom type"
            ) from key
    else:
        structure = config.get(CONF_STRUCTURE)

    if not structure:
        raise vol.Invalid(
            f"Error in sensor {config[CONF_NAME]}. The `{CONF_STRUCTURE}` field can not be empty "
            f"if the parameter `{CONF_DATA_TYPE}` is set to the `{DATA_TYPE_CUSTOM}`"
        )

    try:
        size = struct.calcsize(structure)
    except struct.error as err:
        raise vol.Invalid(
            f"Error in sensor {config[CONF_NAME]} structure: {str(err)}"
        ) from err

    bytecount = config[CONF_COUNT] * 2
    if bytecount != size:
        raise vol.Invalid(
            f"Structure request {size} bytes, "
            f"but {config[CONF_COUNT]} registers have a size of {bytecount} bytes"
        )

    swap_type = config.get(CONF_SWAP)

    if config.get(CONF_SWAP) != CONF_SWAP_NONE:
        if swap_type == CONF_SWAP_BYTE:
            regs_needed = 1
        else:  # CONF_SWAP_WORD_BYTE, CONF_SWAP_WORD
            regs_needed = 2
        if config[CONF_COUNT] < regs_needed or (config[CONF_COUNT] % regs_needed) != 0:
            raise vol.Invalid(
                f"Error in sensor {config[CONF_NAME]} swap({swap_type}) "
                f"not possible due to the registers "
                f"count: {config[CONF_COUNT]}, needed: {regs_needed}"
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
