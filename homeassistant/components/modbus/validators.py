"""Validate Modbus configuration."""
import logging
import struct

from voluptuous import Invalid

from homeassistant.const import CONF_COUNT, CONF_NAME, CONF_STRUCTURE

from .const import (
    CONF_DATA_TYPE,
    CONF_REVERSE_ORDER,
    CONF_SWAP,
    CONF_SWAP_BYTE,
    CONF_SWAP_NONE,
    CONF_SWAP_WORD,
    DATA_TYPE_CUSTOM,
    DATA_TYPE_STRING,
    DEFAULT_STRUCT_FORMAT,
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
        except KeyError:
            raise Invalid(
                f"Unable to detect data type for {config[CONF_NAME]} sensor, try a custom type"
            )
    else:
        structure = config.get(CONF_STRUCTURE)

    if not structure:
        raise Invalid(
            f"Error in sensor {config[CONF_NAME]}. The `{CONF_STRUCTURE}` field can not be empty "
            f"if the parameter `{CONF_DATA_TYPE}` is set to the `{DATA_TYPE_CUSTOM}`"
        )

    try:
        size = struct.calcsize(structure)
    except struct.error as err:
        raise Invalid(f"Error in sensor {config[CONF_NAME]} structure: {str(err)}")

    bytecount = config[CONF_COUNT] * 2
    if bytecount != size:
        raise Invalid(
            f"Structure request {size} bytes, "
            f"but {config[CONF_COUNT]} registers have a size of {bytecount} bytes"
        )

    swap_type = config.get(CONF_SWAP)

    if CONF_REVERSE_ORDER in config:
        if config[CONF_REVERSE_ORDER]:
            swap_type = CONF_SWAP_WORD
        else:
            swap_type = CONF_SWAP_NONE
        del config[CONF_REVERSE_ORDER]

    if config.get(CONF_SWAP) != CONF_SWAP_NONE:
        if swap_type == CONF_SWAP_BYTE:
            regs_needed = 1
        else:  # CONF_SWAP_WORD_BYTE, CONF_SWAP_WORD
            regs_needed = 2
        if config[CONF_COUNT] < regs_needed or (config[CONF_COUNT] % regs_needed) != 0:
            raise Invalid(
                f"Error in sensor {config[CONF_NAME]} swap({swap_type}) "
                f"not possible due to the registers "
                f"count: {config[CONF_COUNT]}, needed: {regs_needed}"
            )

    return {
        **config,
        CONF_STRUCTURE: structure,
        CONF_SWAP: swap_type,
    }
