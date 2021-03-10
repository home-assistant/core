"""Registers builder builds Modbus Save registers based on the HA state."""
import ctypes
import logging

from pymodbus.constants import Endian
from pymodbus.datastore import ModbusSparseDataBlock
from pymodbus.payload import BinaryPayloadBuilder

from .const import DATA_TYPE_FLOAT, DATA_TYPE_INT, DATA_TYPE_STRING, DATA_TYPE_UINT

_LOGGER = logging.getLogger(__name__)


def _build_data_register(value, data_type: int, data_count: int):

    if data_type != DATA_TYPE_STRING and data_count not in [1, 2, 4]:
        assert False, "Modbus Slave support Strings and 16, 32 and 64 bit registers"

    builder = BinaryPayloadBuilder(byteorder=Endian.Big)
    if data_type == DATA_TYPE_FLOAT:
        if data_count == 4:
            builder.add_64bit_float(float(value or 0.0))
        elif data_count == 2:
            builder.add_32bit_float(float(value or 0.0))
        else:
            builder.add_16bit_float(float(value or 0.0))
    elif data_type == DATA_TYPE_INT:
        if data_count == 4:
            builder.add_64bit_int(int(value or 0))
        elif data_count == 2:
            builder.add_32bit_int(int(value or 0))
        else:
            builder.add_16bit_int(int(value or 0))
    elif data_type == DATA_TYPE_UINT:
        if data_count == 4:
            builder.add_64bit_uint(ctypes.c_ulonglong(int(value or 0)).value)
        elif data_count == 2:
            builder.add_32bit_uint(ctypes.c_uint(int(value or 0)).value)
        else:
            builder.add_16bit_uint(ctypes.c_ushort(int(value or 0)).value)
    elif data_type == DATA_TYPE_STRING:
        builder.add_string(value or ("  " * data_count))

    return builder.to_registers()


class RegistersBuilder:
    """Build Modbus Slave registers based on the HA state and the data type."""

    def __init__(self):
        """Init registers builder."""
        self._name = None
        self._address = None
        self._is_binary = None
        self._slave_registers = []

    def name(self, name: str):
        """Store name."""
        self._name = name
        return self

    def address(self, address: int):
        """Store address."""
        self._address = address
        return self

    def with_bit_mask(self, mask: int):
        """Add mask for the binary state."""
        assert self._is_binary, "You should call binary_state before with_bit_mask"
        self._bit_mask = mask
        return self

    def binary_state(self, value, count: int = 1):
        """Register binary state."""
        assert (
            self._is_binary is None
        ), "You can't call binary_state after the state call"
        self._is_binary = True
        self._count = count
        if value == "unavailable":
            value = None
        self._value = bool(value)
        self._bit_mask = 1
        return self

    def state(self, value, data_type: int, count: int):
        """Register data state."""
        assert self._is_binary is None
        self._is_binary = False
        self._count = count
        if value == "unavailable":
            value = None
        self._value = value
        self._data_type = data_type
        return self

    def build(self):
        """Build registers object based on the configuration."""

        def _to_dict(name, address, registers, mask):
            return {
                "name": name,
                "address": address,
                "registers": registers,
                "bit_mask": mask,
            }

        assert self._is_binary is not None, "You should call binary_state or state"
        """Build registers. Return registers, usage bit mask."""
        if self._is_binary:
            masked_value = self._bit_mask if self._value else 0
            registers = [0] * self._count
            registers[-1] = masked_value
            return _to_dict(self._name, self._address, registers, self._bit_mask)

        registers = _build_data_register(self._value, self._data_type, self._count)
        return _to_dict(self._name, self._address, registers, None)


class ModbusSlaveRegisters:
    """Hold slave registers, build register map."""

    def __init__(self, slave):
        """Init slave registers class."""
        self._slave = slave
        self._registers = []

    def add_slave_configuration(self, configure_lambda):
        """Add slave confguration through the RegistersBuilder."""
        builder = RegistersBuilder()
        configure_lambda(builder)
        self._registers.append(builder.build())

    def build_register_map(self):
        """Build a register map for the slave."""
        server_registers = {}
        for registers_item in self._registers:
            _LOGGER.warning(
                "build_register_map %s %s %s %s",
                registers_item["name"],
                registers_item["address"],
                registers_item["registers"],
                registers_item["bit_mask"],
            )
            for idx, register_data in enumerate(registers_item["registers"]):
                self._process_register(
                    server_registers, registers_item, register_data, idx
                )

        return {address: server_registers[address][0] for address in server_registers}

    def _process_register(self, server_registers, registers_item, register_data, idx):
        address = registers_item["address"] + idx
        if registers_item["bit_mask"] is None:
            if address in server_registers:
                _LOGGER.error(
                    "Modbus slave entity `%s` register %d overlaps with the already registered entities",
                    registers_item["name"],
                    address,
                )
                return None
            server_registers[address] = [register_data, 0xFFFF]
        else:
            shift_bits = idx * 16
            bit_mask = (
                int(registers_item["bit_mask"]) & (0xFFFF << shift_bits)
            ) >> shift_bits
            # Skip register entirely if the bit mask has no set bits in this word
            if bit_mask > 0:
                # value_data represent a turned on bits in the result register if state is ON
                value_data = bit_mask if register_data else 0
                if address in server_registers:
                    # mask holds the used positions, value holds combined bit mask for the slave
                    value, mask = server_registers[address]
                    if mask & bit_mask > 0:
                        _LOGGER.error(
                            "Modbus slave entity `%s` register %d bit mask %d overlaps with the already registered entities",
                            registers_item["name"],
                            address,
                            bit_mask,
                        )
                        return None
                    # update resulting register value and used bits mask
                    server_registers[address] = [
                        value | value_data,
                        mask | bit_mask,
                    ]
                else:
                    server_registers[address] = [value_data, bit_mask]


class ModbusSlavesHolder:
    """Holds an assoc map of the Modbus Slave address and registers map."""

    def __init__(self):
        """Init the holder."""
        self._slaves = {}

    def add_slave_configuration(self, slave, configure_lambda):
        """Get the ModbusSlaveRegisters instance based on the slave."""
        if slave not in self._slaves:
            self._slaves[slave] = ModbusSlaveRegisters(slave)

        self._slaves[slave].add_slave_configuration(configure_lambda)

    def build_server_blocks(self):
        """Return assoc map with the Modbus Slave address and register map."""
        return {
            slave: ModbusSparseDataBlock(self._slaves[slave].build_register_map())
            for slave in self._slaves
        }
