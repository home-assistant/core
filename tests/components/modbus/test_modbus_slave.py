"""Test modbus_slave module."""
import pytest

from homeassistant.components.modbus.const import (
    DATA_TYPE_FLOAT,
    DATA_TYPE_INT,
    DATA_TYPE_STRING,
    DATA_TYPE_UINT,
)
from homeassistant.components.modbus.modbus_slave import RegistersBuilder


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
                "registers": [0, 0, 0, 0x20],
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
