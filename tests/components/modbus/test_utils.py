"""The tests for the Modbus sensor component."""
import json
import logging
from unittest import mock

import pytest

from homeassistant.components.modbus.const import (
    DATA_TYPE_FLOAT,
    DATA_TYPE_INT,
    DATA_TYPE_STRING,
    DATA_TYPE_UINT,
)
from homeassistant.components.modbus.utils import build_registers, build_server_blocks

from tests.common import load_fixture


@pytest.mark.parametrize(
    "state,data_type,data_count,expected",
    [
        ("unavailable", DATA_TYPE_FLOAT, 4, [0, 0]),
        ("unavailable", DATA_TYPE_FLOAT, 2, [0]),
        (3.14152653, DATA_TYPE_FLOAT, 4, [16457, 3781]),
        (3.14152653, DATA_TYPE_FLOAT, 2, [16968]),
        (-3.14152653, DATA_TYPE_FLOAT, 4, [49225, 3781]),
        (-3.14152653, DATA_TYPE_FLOAT, 2, [49736]),
        ("unavailable", DATA_TYPE_INT, 4, [0, 0]),
        ("unavailable", DATA_TYPE_INT, 2, [0]),
        (123456789, DATA_TYPE_INT, 4, [1883, 52501]),
        (32000, DATA_TYPE_INT, 2, [32000]),
        (-123456789, DATA_TYPE_INT, 4, [63652, 13035]),
        (-32000, DATA_TYPE_INT, 2, [33536]),
        ("unavailable", DATA_TYPE_UINT, 4, [0, 0]),
        ("unavailable", DATA_TYPE_UINT, 2, [0]),
        (123456789, DATA_TYPE_UINT, 4, [1883, 52501]),
        (32000, DATA_TYPE_UINT, 2, [32000]),
        (-123456789, DATA_TYPE_UINT, 4, [63652, 13035]),
        (-32000, DATA_TYPE_UINT, 2, [33536]),
        (
            "unavailable",
            DATA_TYPE_STRING,
            4,
            # 4 spaces
            [8224, 8224],
        ),
        ("test", DATA_TYPE_STRING, 4, [29797, 29556]),
        (
            "overflow",
            DATA_TYPE_STRING,
            4,
            # Should add a full string. build_server_blocks should control address overlap
            [28534, 25970, 26220, 28535],
        ),
    ],
)
def test_build_registers(state, data_type, data_count, expected):
    """Test build registers."""
    assert build_registers(state, data_type, data_count) == expected


@pytest.mark.parametrize(
    "fixture,expected_error",
    [
        ("registers_no_overlap.json", None),
        (
            "registers_with_overlap.json",
            (
                "Modbus slave entity `%s` register %d overlaps with the already registered entities",
                "Modbus Unit 77 register 25",
                27,
            ),
        ),
        ("registers_mask_no_overlap.json", None),
        (
            "registers_mask_overlap_bit.json",
            (
                "Modbus slave entity `%s` register %d bit mask %d overlaps with the already registered entities",
                "Modbus Unit 77 register 27 bit 1 ON (overlapping OFFed bit mask 0x2)",
                27,
                2,
            ),
        ),
        (
            "registers_mask_overlap_bit_with_regular.json",
            (
                "Modbus slave entity `%s` register %d bit mask %d overlaps with the already registered entities",
                "Modbus Unit 77 register 31 bit 0 OFF (overlap with 28-32)",
                31,
                1,
            ),
        ),
    ],
)
def test_build_server_blocks(fixture, expected_error):
    """Test server blocks."""
    entities, result = json.loads(load_fixture(f"modbus/{fixture}"))

    if expected_error is not None:
        logger = logging.getLogger("homeassistant.components.modbus.utils")
        with mock.patch.object(logger, "error") as mock_error:
            build_server_blocks(entities)
            mock_error.assert_called_with(*expected_error)
    else:
        blocks = build_server_blocks(entities)
        dict_val = {unit: blocks[unit].values for unit in blocks}
        # int keys to string keys recursive conversion to make it JSON compatible
        assert json.loads(json.dumps(dict_val)) == result
