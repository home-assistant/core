"""Utility methods."""
import ctypes
import logging

from pymodbus.constants import Endian
from pymodbus.datastore import ModbusSparseDataBlock
from pymodbus.payload import BinaryPayloadBuilder

from .const import DATA_TYPE_FLOAT, DATA_TYPE_INT, DATA_TYPE_STRING, DATA_TYPE_UINT

_LOGGER = logging.getLogger(__name__)


def build_registers(state, data_type, data_count):
    """Build Modbus slave register array based on the data type, length and previous state."""
    builder = BinaryPayloadBuilder(byteorder=Endian.Big)
    if state == "unavailable":
        state = None
    if data_type == DATA_TYPE_FLOAT:
        if data_count == 4:
            builder.add_32bit_float(float(state or 0.0))
        else:
            builder.add_16bit_float(float(state or 0.0))
    elif data_type == DATA_TYPE_INT:
        if data_count == 4:
            builder.add_32bit_int(int(state or 0))
        else:
            builder.add_16bit_int(int(state or 0))
    elif data_type == DATA_TYPE_UINT:
        if data_count == 4:
            builder.add_32bit_uint(ctypes.c_uint(int(state or 0)).value)
        else:
            builder.add_16bit_uint(ctypes.c_ushort(int(state or 0)).value)
    elif data_type == DATA_TYPE_STRING:
        builder.add_string(state or (" " * data_count))

    return builder.to_registers()


def build_server_blocks(entities):
    """Build Modbus slave server block, check unit address overlap."""

    def _process_data_item(entity, server_registers, data_item, idx):
        if "bit_mask" not in entity:
            if register in server_registers:
                _LOGGER.error(
                    "Modbus slave entity `%s` register %d overlaps with the already registered entities",
                    entity["name"],
                    register,
                )
                return None
            server_registers[register] = [data_item, 0xFFFF]
        else:
            shift_bits = idx * 16
            bit_mask = (int(entity["bit_mask"]) & (0xFFFF << shift_bits)) >> shift_bits
            # Skip register entirely if the bit mask has no set bits in this word
            if bit_mask > 0:
                # value_data represent a turned on bits in the result register if state is ON
                value_data = bit_mask if data_item else 0
                if register in server_registers:
                    # mask holds the used positions, value holds combined bit mask for the slave
                    value, mask = server_registers[register]
                    if mask & bit_mask > 0:
                        _LOGGER.error(
                            "Modbus slave entity `%s` register %d bit mask %d overlaps with the already registered entities",
                            entity["name"],
                            register,
                            bit_mask,
                        )
                        return None
                    # update resulting register value and used bits mask
                    server_registers[register] = [
                        value | value_data,
                        mask | bit_mask,
                    ]
                else:
                    server_registers[register] = [value_data, bit_mask]

    assoc_array = {}
    for entity in entities:
        register = int(entity["register"])
        unit_address = int(entity["unit"])
        assoc_array[unit_address] = server_registers = assoc_array.get(unit_address, {})

        for idx, data_item in enumerate(entity["data"]):
            _process_data_item(entity, server_registers, data_item, idx)
            register = register + 1

    def _strip_bit_maks(registers):
        result = {}
        for register in registers:
            item = registers[register]
            result[register] = item[0] if isinstance(item, list) else item
        return result

    return {
        unit_address: ModbusSparseDataBlock(_strip_bit_maks(assoc_array[unit_address]))
        for unit_address in assoc_array
    }
