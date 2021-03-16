"""Test modbus_slave module."""
import pytest

from homeassistant.components.modbus.const import (
    DATA_TYPE_FLOAT,
    DATA_TYPE_INT,
    DATA_TYPE_STRING,
    DATA_TYPE_UINT,
)
from homeassistant.components.modbus.modbus_slave import (
    ModbusSlaveRegisters,
    ModbusSlavesHolder,
    RegistersBuilder,
)


@pytest.mark.parametrize(
    "configure_lambda,expected",
    [
        (
            lambda builder: builder.name("test"),
            "You should call binary_state or state",
        ),
        (
            lambda builder: builder.name("test").address(55),
            "You should call binary_state or state",
        ),
        (
            lambda builder: builder.name("test").address(55).with_bit_mask(0x20),
            "You should call binary_state before with_bit_mask",
        ),
        (
            lambda builder: builder.name("test")
            .address(55)
            .state(3.1415192653, DATA_TYPE_FLOAT, 1),
            {"address": 55, "bit_mask": None, "name": "test", "registers": [16968]},
        ),
        (
            lambda builder: builder.name("test")
            .address(55)
            .state(3.1415192653, DATA_TYPE_FLOAT, 2),
            {
                "address": 55,
                "bit_mask": None,
                "name": "test",
                "registers": [16457, 3751],
            },
        ),
        (
            lambda builder: builder.name("test")
            .address(55)
            .state(3.1415192653, DATA_TYPE_FLOAT, 4),
            {
                "address": 55,
                "bit_mask": None,
                "name": "test",
                "registers": [16393, 8660, 55873, 48469],
            },
        ),
        (
            lambda builder: builder.name("test")
            .address(55)
            .state(3.1415192653, DATA_TYPE_FLOAT, 8),
            "Modbus Slave support Strings and 16, 32 and 64 bit registers",
        ),
        (
            lambda builder: builder.name("test")
            .address(55)
            .state(32767, DATA_TYPE_INT, 1),
            {"address": 55, "bit_mask": None, "name": "test", "registers": [32767]},
        ),
        (
            lambda builder: builder.name("test")
            .address(55)
            .state(65535, DATA_TYPE_INT, 1),
            "format requires -32768 <= number <= 32767",
        ),
        (
            lambda builder: builder.name("test")
            .address(55)
            .state(65535, DATA_TYPE_INT, 2),
            {"address": 55, "bit_mask": None, "name": "test", "registers": [0, 65535]},
        ),
        (
            lambda builder: builder.name("test")
            .address(55)
            .state(0x0FFFFFFFFFFFFFFF, DATA_TYPE_INT, 4),
            {
                "address": 55,
                "bit_mask": None,
                "name": "test",
                "registers": [4095, 65535, 65535, 65535],
            },
        ),
        (
            lambda builder: builder.name("test")
            .address(55)
            .state(0xFFFFFFFFFFFFFFFF, DATA_TYPE_UINT, 4),
            {
                "address": 55,
                "bit_mask": None,
                "name": "test",
                "registers": [65535, 65535, 65535, 65535],
            },
        ),
        (
            lambda builder: builder.name("test")
            .address(55)
            .state(0xBADBEEF, DATA_TYPE_UINT, 2),
            {
                "address": 55,
                "bit_mask": None,
                "name": "test",
                "registers": [2989, 48879],
            },
        ),
        (
            lambda builder: builder.name("test")
            .address(55)
            .state(0xBADB, DATA_TYPE_UINT, 1),
            {"address": 55, "bit_mask": None, "name": "test", "registers": [47835]},
        ),
        (
            lambda builder: builder.name("test")
            .address(55)
            .state("Modbus", DATA_TYPE_STRING, 3),
            {
                "address": 55,
                "bit_mask": None,
                "name": "test",
                "registers": [19823, 25698, 30067],
            },
        ),
        (
            lambda builder: builder.name("test")
            .address(55)
            .state("unavailable", DATA_TYPE_STRING, 3),
            # unavailable renders to all spaces
            {
                "address": 55,
                "bit_mask": None,
                "name": "test",
                "registers": [0x2020, 0x2020, 0x2020],
            },
        ),
        (
            lambda builder: builder.name("test")
            .address(55)
            .state("unavailable", DATA_TYPE_UINT, 4),
            # unavailable renders to all zeros
            {
                "address": 55,
                "bit_mask": None,
                "name": "test",
                "registers": [0, 0, 0, 0],
            },
        ),
        (
            lambda builder: builder.name("test")
            .address(55)
            .state(1, DATA_TYPE_UINT, 1)
            .binary_state(1, 1),
            "You can't call binary_state after the state call",
        ),
        (
            lambda builder: builder.name("test").address(55).binary_state(True, 1),
            {
                "address": 55,
                "bit_mask": 1,
                "name": "test",
                "registers": [1],
            },
        ),
        (
            lambda builder: builder.name("test").address(55).binary_state(False, 1),
            {
                "address": 55,
                "bit_mask": 1,
                "name": "test",
                "registers": [0],
            },
        ),
        (
            lambda builder: builder.name("test")
            .address(55)
            .binary_state(True, 1)
            .with_bit_mask(0x20),
            {
                "address": 55,
                "bit_mask": 0x20,
                "name": "test",
                "registers": [0x20],
            },
        ),
        (
            lambda builder: builder.name("test")
            .address(55)
            .binary_state(True, 4)
            .with_bit_mask(0x20),
            {
                "address": 55,
                "bit_mask": 0x20,
                "name": "test",
                "registers": [0x20, 0, 0, 0],
            },
        ),
        (
            lambda builder: builder.name("test")
            .address(55)
            .binary_state(True, 1)
            .with_bit_mask(0x60),
            {
                "address": 55,
                "bit_mask": 0x60,
                "name": "test",
                "registers": [0x60],
            },
        ),
    ],
)
def test_register_builder(configure_lambda, expected):
    """Test RegistersBuilder class."""
    instance = RegistersBuilder()
    if isinstance(expected, str):
        with pytest.raises(Exception) as excinfo:
            configure_lambda(instance)
            instance.build()
        assert expected in str(excinfo)
    else:
        configure_lambda(instance)
        assert expected == instance.build()


@pytest.mark.parametrize(
    "configure_lambdas,expected",
    [
        (
            [
                lambda builder: builder.name("simple uint test")
                .address(55)
                .state(0xBADBEEF, DATA_TYPE_UINT, 2)
            ],
            {55: 0xBAD, 56: 0xBEEF},
        ),
        (
            [
                lambda builder: builder.name("overlapping uint test1")
                .address(55)
                .state(0xBADBEEF, DATA_TYPE_UINT, 2),
                lambda builder: builder.name("overlapping uint test2")
                .address(56)
                .state(0xBADBEEF, DATA_TYPE_UINT, 2),
            ],
            "Modbus slave entity `overlapping uint test2` register 56 overlaps with the already registered entities",
        ),
        (
            [
                lambda builder: builder.name("55,56, uints")
                .address(55)
                .state(0xBADBEEF, DATA_TYPE_UINT, 2),
                lambda builder: builder.name("57 uint")
                .address(57)
                .state(0xEE, DATA_TYPE_UINT, 1),
            ],
            {55: 0xBAD, 56: 0xBEEF, 57: 0xEE},
        ),
        (
            [
                lambda builder: builder.name("register 27 bit 0 ON")
                .address(27)
                .binary_state(True, 1)
                .with_bit_mask(0x01),
                lambda builder: builder.name("register 27 bit 1 OFF")
                .address(27)
                .binary_state(False, 1)
                .with_bit_mask(0x02),
                lambda builder: builder.name("register 27 bit 2 ON")
                .address(27)
                .binary_state(True, 1)
                .with_bit_mask(0x04),
                lambda builder: builder.name("register 28, 4 words")
                .address(28)
                .state(0x0033003400350036, DATA_TYPE_UINT, 4),
                lambda builder: builder.name(
                    "register 32 (mask is 0xFF00_0000 so skip reg 32 and set reg 33 to 0xFF00 which is 65280)"
                )
                .address(32)
                .binary_state(True, 2)
                .with_bit_mask(0xFF000000),
                lambda builder: builder.name(
                    "register 32 (reg 32 not occupied by the ^^ due to the 0xFF00_0000 mask) so we can reuse reg 32"
                )
                .address(32)
                .state(48000, DATA_TYPE_UINT, 1),
                lambda builder: builder.name("register 34")
                .address(34)
                .binary_state(True, 4)
                .with_bit_mask(0xF00FFFFFFFFFFFFF),
                lambda builder: builder.name("register 25")
                .address(25)
                .state(44, DATA_TYPE_UINT, 1),
            ],
            {
                25: 44,
                27: 5,
                28: 0x33,
                29: 0x34,
                30: 0x35,
                31: 0x36,
                32: 48000,
                33: 0xFF00,
                34: 0xFFFF,
                35: 0xFFFF,
                36: 0xFFFF,
                37: 0xF00F,
            },
        ),
        (
            [
                lambda builder: builder.name("register 27 bit 0 ON")
                .address(27)
                .binary_state(True, 1)
                .with_bit_mask(0x01),
                lambda builder: builder.name("register 27 bit 1 OFF")
                .address(27)
                .binary_state(False, 1)
                .with_bit_mask(0x02),
                lambda builder: builder.name("register 27 bit 2 ON")
                .address(27)
                .binary_state(True, 1)
                .with_bit_mask(0x04),
                lambda builder: builder.name(
                    "register 27 bit 1 ON (overlapping OFFed bit mask 0x2)"
                )
                .address(27)
                .binary_state(True, 1)
                .with_bit_mask(0x02),
            ],
            "Modbus slave entity `register 27 bit 1 ON (overlapping OFFed bit mask 0x2)` register 27 bit mask 2 overlaps with the already registered entities",
        ),
        (
            [
                lambda builder: builder.name("register 28")
                .address(28)
                .state(0, DATA_TYPE_UINT, 4),
                lambda builder: builder.name(
                    "register 31 bit 0 OFF (overlap with 28-32)"
                )
                .address(31)
                .binary_state(False, 1)
                .with_bit_mask(0x01),
            ],
            "Modbus slave entity `register 31 bit 0 OFF (overlap with 28-32)` register 31 bit mask 1 overlaps with the already registered entities",
        ),
        (
            [
                lambda builder: builder.name("register 31")
                .address(31)
                .binary_state(False, 2)
                .with_bit_mask(0xF0000001),
                lambda builder: builder.name("register 32")
                .address(32)
                .state(0, DATA_TYPE_UINT, 4),
            ],
            "Modbus slave entity `register 32` register 32 overlaps with the already registered entities",
        ),
        (
            [
                lambda builder: builder.name("register 31 (2 words, second unused)")
                .address(31)
                .binary_state(False, 2)
                .with_bit_mask(0x01),
                lambda builder: builder.name("register 32")
                .address(32)
                .state(1, DATA_TYPE_UINT, 4),
            ],
            {31: 0, 32: 0, 33: 0, 34: 0, 35: 1},
        ),
    ],
)
def test_slave_registers_builder(configure_lambdas, expected):
    """Test slave register builder."""

    registers = ModbusSlaveRegisters()
    if isinstance(expected, str):
        with pytest.raises(AssertionError) as ex:
            for cfg_lambda in configure_lambdas:
                registers.add_slave_configuration(cfg_lambda)
            registers.build_register_map()
        assert expected in str(ex)
    else:
        for cfg_lambda in configure_lambdas:
            registers.add_slave_configuration(cfg_lambda)
        assert registers.build_register_map() == expected


@pytest.mark.parametrize(
    "slaves,expected",
    [
        (
            {
                77: [
                    lambda builder: builder.name("slave 77, register 31")
                    .address(31)
                    .binary_state(True, 2)
                    .with_bit_mask(0xF0),
                    lambda builder: builder.name("slave 77, register 32")
                    .address(32)
                    .state(5, DATA_TYPE_UINT, 4),
                ],
                78: [
                    lambda builder: builder.name("slave 78, register 31")
                    .address(31)
                    .state(0x80, DATA_TYPE_UINT, 1),
                ],
            },
            {77: {31: 0xF0, 32: 0, 33: 0, 34: 0, 35: 5}, 78: {31: 128}},
        ),
    ],
)
def test_slaves_holder(slaves, expected):
    """Test ModbusModbusSparseDataBlock generation."""

    def _run():
        holder = ModbusSlavesHolder()
        for unit in slaves:
            for cfg_lambda in slaves[unit]:
                holder.add_slave_configuration(unit, cfg_lambda)
        blocks = holder.build_server_blocks()
        return {key: blocks[key].values for key in blocks}

    if isinstance(expected, str):
        with pytest.raises(AssertionError) as ex:
            _run()
        assert expected in str(ex)
    else:
        assert _run() == expected
