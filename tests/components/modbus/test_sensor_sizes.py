"""The tests for the Modbus sensor component."""

import pytest

from homeassistant.components.modbus.const import (
    CONF_DATA_TYPE,
    CONF_MAX_VALUE,
    CONF_MIN_VALUE,
    CONF_NAN_VALUE,
    CONF_PRECISION,
    CONF_REGISTER_SIZE_BYTES,
    CONF_SCALE,
    CONF_SLAVE_COUNT,
    CONF_SWAP,
    CONF_SWAP_BYTE,
    CONF_SWAP_WORD,
    CONF_SWAP_WORD_BYTE,
    CONF_VIRTUAL_COUNT,
    CONF_ZERO_SUPPRESS,
    DataType,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_COUNT,
    CONF_NAME,
    CONF_OFFSET,
    CONF_SENSORS,
    CONF_STRUCTURE,
    CONF_UNIQUE_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import TEST_ENTITY_NAME

ENTITY_ID = f"{SENSOR_DOMAIN}.{TEST_ENTITY_NAME}".replace(" ", "_")
SLAVE_UNIQUE_ID = "ground_floor_sensor"


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 201,
                },
            ],
        }
    ],
)
@pytest.mark.parametrize(
    ("config_addon", "expected_count"),
    [
        (
            {
                CONF_DATA_TYPE: DataType.UINT16,
                CONF_REGISTER_SIZE_BYTES: 2,
            },
            1,
        ),
        (
            {
                CONF_DATA_TYPE: DataType.UINT32,
                CONF_REGISTER_SIZE_BYTES: 2,
            },
            2,
        ),
        (
            {
                CONF_DATA_TYPE: DataType.UINT64,
                CONF_REGISTER_SIZE_BYTES: 2,
            },
            4,
        ),
        (
            {
                CONF_DATA_TYPE: DataType.UINT32,
                CONF_REGISTER_SIZE_BYTES: 4,
            },
            1,
        ),
        (
            {
                CONF_DATA_TYPE: DataType.FLOAT64,
                CONF_REGISTER_SIZE_BYTES: 4,
            },
            2,
        ),
        (
            {
                CONF_DATA_TYPE: DataType.FLOAT64,
                CONF_REGISTER_SIZE_BYTES: 8,
            },
            1,
        ),
        (
            {
                CONF_DATA_TYPE: DataType.CUSTOM,
                CONF_COUNT: 1,
                CONF_REGISTER_SIZE_BYTES: 4,
                CONF_STRUCTURE: ">L",
            },
            1,
        ),
        (
            {
                CONF_DATA_TYPE: DataType.CUSTOM,
                CONF_COUNT: 2,
                CONF_REGISTER_SIZE_BYTES: 2,
                CONF_STRUCTURE: ">L",
            },
            2,
        ),
        (
            {
                CONF_DATA_TYPE: DataType.CUSTOM,
                CONF_COUNT: 1,
                CONF_REGISTER_SIZE_BYTES: 8,
                CONF_STRUCTURE: ">Q",
            },
            1,
        ),
        (
            {
                CONF_DATA_TYPE: DataType.CUSTOM,
                CONF_COUNT: 2,
                CONF_REGISTER_SIZE_BYTES: 4,
                CONF_STRUCTURE: ">Q",
            },
            2,
        ),
        (
            {
                CONF_DATA_TYPE: DataType.CUSTOM,
                CONF_COUNT: 4,
                CONF_REGISTER_SIZE_BYTES: 2,
                CONF_STRUCTURE: ">Q",
            },
            4,
        ),
    ],
)
async def test_count_is_correct_when_register_bytes_is_set(
    hass: HomeAssistant, mock_do_cycle, expected_count
) -> None:
    """Run test to check the sensor count is correctly set for the given register size in bytes."""
    test_sensor = hass.data["sensor"].config["modbus"][0]["sensors"][0]
    assert expected_count == test_sensor["count"]


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 201,
                },
            ],
        }
    ],
)
@pytest.mark.parametrize(
    ("config_addon", "expected_count"),
    [
        (
            {
                CONF_DATA_TYPE: DataType.UINT16,
            },
            1,
        ),
        (
            {
                CONF_DATA_TYPE: DataType.UINT32,
            },
            2,
        ),
        (
            {
                CONF_DATA_TYPE: DataType.UINT64,
            },
            4,
        ),
        (
            {
                CONF_DATA_TYPE: DataType.CUSTOM,
                CONF_COUNT: 2,
                CONF_STRUCTURE: ">L",
            },
            2,
        ),
    ],
)
async def test_count_is_correct_when_register_bytes_is_not_set(
    hass: HomeAssistant, mock_do_cycle, expected_count
) -> None:
    """Run test to check the sensor count is correctly when given register size is not set."""
    test_sensor = hass.data["sensor"].config["modbus"][0]["sensors"][0]
    assert expected_count == test_sensor["count"]


@pytest.mark.parametrize("check_config_loaded", [False])
@pytest.mark.parametrize(
    ("do_config", "error_message"),
    [
        (
            {
                CONF_SENSORS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 1234,
                        CONF_DATA_TYPE: DataType.UINT16,
                        CONF_REGISTER_SIZE_BYTES: 4,
                    },
                ]
            },
            "test entity: `register_size_bytes: 4` cannot be specified with `data_type: DataType.UINT16`",
        ),
        (
            {
                CONF_SENSORS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 1234,
                        CONF_DATA_TYPE: DataType.UINT32,
                        CONF_REGISTER_SIZE_BYTES: 8,
                    },
                ]
            },
            "test entity: `register_size_bytes: 8` cannot be specified with `data_type: DataType.UINT32`",
        ),
        (
            {
                CONF_SENSORS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 1234,
                        CONF_DATA_TYPE: DataType.CUSTOM,
                        CONF_REGISTER_SIZE_BYTES: 8,
                        CONF_STRUCTURE: ">L",
                        CONF_COUNT: 1,
                    },
                ]
            },
            "test entity: Size of structure is 4 bytes but `count: 1` is 8 bytes",
        ),
        (
            {
                CONF_SENSORS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 1234,
                        CONF_DATA_TYPE: DataType.CUSTOM,
                        CONF_REGISTER_SIZE_BYTES: 4,
                        CONF_STRUCTURE: ">L",
                        CONF_COUNT: 2,
                    },
                ]
            },
            "test entity: Size of structure is 4 bytes but `count: 2` is 8 bytes",
        ),
        (
            {
                CONF_SENSORS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 1234,
                        CONF_DATA_TYPE: DataType.CUSTOM,
                        CONF_REGISTER_SIZE_BYTES: 2,
                        CONF_STRUCTURE: ">L",
                        CONF_COUNT: 3,
                    },
                ]
            },
            "test entity: Size of structure is 4 bytes but `count: 3` is 6 bytes",
        ),
        (
            {
                CONF_SENSORS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 1234,
                        CONF_DATA_TYPE: DataType.UINT32,
                        CONF_REGISTER_SIZE_BYTES: 0,
                    },
                ]
            },
            "test entity: Zero or odd numbers are not valid register sizes.",
        ),
        (
            {
                CONF_SENSORS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 1234,
                        CONF_DATA_TYPE: DataType.UINT32,
                        CONF_REGISTER_SIZE_BYTES: 1,
                    },
                ]
            },
            "test entity: Zero or odd numbers are not valid register sizes.",
        ),
        (
            {
                CONF_SENSORS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 1234,
                        CONF_DATA_TYPE: DataType.UINT32,
                        CONF_REGISTER_SIZE_BYTES: 17,
                    },
                ]
            },
            "test entity: Zero or odd numbers are not valid register sizes.",
        ),
        (
            {
                CONF_SENSORS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 1234,
                        CONF_DATA_TYPE: DataType.UINT32,
                        CONF_REGISTER_SIZE_BYTES: 10,
                    },
                ]
            },
            "test entity: `register_size_bytes:10` is not valid, only 2, 4 or 8 are valid.",
        ),
        (
            {
                CONF_SENSORS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 1234,
                        CONF_DATA_TYPE: DataType.STRING,
                        CONF_REGISTER_SIZE_BYTES: 4,
                        CONF_COUNT: 2,
                    },
                ]
            },
            "test entity: `register_size_bytes: 4` cannot be specified with `data_type: DataType.STRING`",
        ),
        (
            {
                CONF_SENSORS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 1234,
                        CONF_DATA_TYPE: DataType.STRING,
                        CONF_REGISTER_SIZE_BYTES: 8,
                        CONF_COUNT: 2,
                    },
                ]
            },
            "test entity: `register_size_bytes: 8` cannot be specified with `data_type: DataType.STRING`",
        ),
    ],
)
async def test_register_bytes_incorrectly_set(
    hass: HomeAssistant, error_message, mock_modbus, caplog: pytest.LogCaptureFixture
) -> None:
    """Run test for sensor with wrong register size in bytes."""
    messages = str([x.message for x in caplog.get_records("setup")])
    assert error_message in messages


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                },
            ],
        },
    ],
)
@pytest.mark.parametrize(
    ("config_addon", "register_words", "do_exception", "expected"),
    [
        (
            {
                CONF_DATA_TYPE: DataType.INT32,
                CONF_REGISTER_SIZE_BYTES: 4,
                CONF_SCALE: 1,
                CONF_OFFSET: 0,
                CONF_PRECISION: 0,
            },
            [0x89ABCDEF],
            False,
            "-1985229329",
        ),
        (
            {
                CONF_DATA_TYPE: DataType.UINT64,
                CONF_SCALE: 1,
                CONF_OFFSET: 0,
                CONF_PRECISION: 0,
                CONF_REGISTER_SIZE_BYTES: 4,
            },
            [0x89ABCDEF, 0x01234567],
            False,
            "9920249030613615975",
        ),
        (
            {
                CONF_DATA_TYPE: DataType.UINT64,
                CONF_SCALE: 1,
                CONF_OFFSET: 0,
                CONF_PRECISION: 0,
                CONF_REGISTER_SIZE_BYTES: 8,
            },
            [0x89ABCDEF01234567],
            False,
            "9920249030613615975",
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT32,
                CONF_SWAP: CONF_SWAP_BYTE,
                CONF_REGISTER_SIZE_BYTES: 4,
            },
            [0x01020304],
            False,
            str(0x04030201),
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT32,
                CONF_SWAP: CONF_SWAP_WORD,
                CONF_REGISTER_SIZE_BYTES: 4,
            },
            [0x01020304],
            False,
            str(0x01020304),
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT32,
                CONF_SWAP: CONF_SWAP_WORD_BYTE,
                CONF_REGISTER_SIZE_BYTES: 4,
            },
            [0x01020304],
            False,
            str(0x04030201),
        ),
        (
            {
                CONF_DATA_TYPE: DataType.UINT64,
                CONF_SCALE: 1,
                CONF_OFFSET: 0,
                CONF_PRECISION: 0,
                CONF_REGISTER_SIZE_BYTES: 4,
                CONF_SWAP: CONF_SWAP_BYTE,
            },
            [0x89ABCDEF, 0x01234567],
            False,
            str(0xEFCDAB8967452301),
        ),
        (
            {
                CONF_DATA_TYPE: DataType.UINT64,
                CONF_SCALE: 1,
                CONF_OFFSET: 0,
                CONF_PRECISION: 0,
                CONF_REGISTER_SIZE_BYTES: 4,
                CONF_SWAP: CONF_SWAP_WORD,
            },
            [0x89ABCDEF, 0x01234567],
            False,
            str(0x0123456789ABCDEF),
        ),
        (
            {
                CONF_DATA_TYPE: DataType.UINT64,
                CONF_SCALE: 1,
                CONF_OFFSET: 0,
                CONF_PRECISION: 0,
                CONF_REGISTER_SIZE_BYTES: 4,
                CONF_SWAP: CONF_SWAP_WORD_BYTE,
            },
            [0x89ABCDEF, 0x01234567],
            False,
            str(0x67452301EFCDAB89),
        ),
        (
            {
                CONF_DATA_TYPE: DataType.UINT64,
                CONF_SCALE: 1,
                CONF_OFFSET: 0,
                CONF_PRECISION: 0,
                CONF_REGISTER_SIZE_BYTES: 8,
                CONF_SWAP: CONF_SWAP_BYTE,
            },
            [0x89ABCDEF01234567],
            False,
            str(0x67452301EFCDAB89),
        ),
        (
            {
                CONF_DATA_TYPE: DataType.UINT64,
                CONF_SCALE: 1,
                CONF_OFFSET: 0,
                CONF_PRECISION: 0,
                CONF_REGISTER_SIZE_BYTES: 8,
                CONF_SWAP: CONF_SWAP_WORD,
            },
            [0x89ABCDEF01234567],
            False,
            str(0x89ABCDEF01234567),
        ),
        (
            {
                CONF_DATA_TYPE: DataType.UINT64,
                CONF_SCALE: 1,
                CONF_OFFSET: 0,
                CONF_PRECISION: 0,
                CONF_REGISTER_SIZE_BYTES: 8,
                CONF_SWAP: CONF_SWAP_WORD_BYTE,
            },
            [0x89ABCDEF01234567],
            False,
            str(0x67452301EFCDAB89),
        ),
    ],
)
async def test_sensor_state_when_register_size_not_two_bytes(
    hass: HomeAssistant, mock_do_cycle, expected
) -> None:
    """Run test for sensor state when register size is not two bytes."""
    assert hass.states.get(ENTITY_ID).state == expected


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                },
            ],
        },
    ],
)
@pytest.mark.parametrize(
    ("config_addon", "register_words", "do_exception", "expected"),
    [
        (
            {
                CONF_SLAVE_COUNT: 1,
                CONF_DATA_TYPE: DataType.FLOAT32,
                CONF_UNIQUE_ID: SLAVE_UNIQUE_ID,
                CONF_REGISTER_SIZE_BYTES: 4,
            },
            [0x51020304, 0x51020304],
            False,
            ["34899771392", "34899771392"],
        ),
        (
            {
                CONF_VIRTUAL_COUNT: 1,
                CONF_DATA_TYPE: DataType.FLOAT32,
                CONF_UNIQUE_ID: SLAVE_UNIQUE_ID,
                CONF_REGISTER_SIZE_BYTES: 4,
            },
            [0x51020304, 0x51020304],
            False,
            ["34899771392", "34899771392"],
        ),
        (
            {
                CONF_SLAVE_COUNT: 2,
                CONF_DATA_TYPE: DataType.FLOAT32,
                CONF_UNIQUE_ID: SLAVE_UNIQUE_ID,
                CONF_REGISTER_SIZE_BYTES: 4,
            },
            [0x51020304, 0x51020304, 0x51020304],
            False,
            ["34899771392", "34899771392", "34899771392"],
        ),
        (
            {
                CONF_VIRTUAL_COUNT: 2,
                CONF_DATA_TYPE: DataType.FLOAT32,
                CONF_UNIQUE_ID: SLAVE_UNIQUE_ID,
                CONF_REGISTER_SIZE_BYTES: 4,
            },
            [0x51020304, 0x51020304, 0x51020304],
            False,
            ["34899771392", "34899771392", "34899771392"],
        ),
        (
            {
                CONF_SLAVE_COUNT: 3,
                CONF_DATA_TYPE: DataType.UINT64,
                CONF_UNIQUE_ID: SLAVE_UNIQUE_ID,
                CONF_REGISTER_SIZE_BYTES: 4,
            },
            [
                0x51020304,
                0x51020304,
                0x51020304,
                0x51020304,
                0x51020304,
                0x51020304,
                0x51020304,
                0x51020304,
            ],
            False,
            [
                str(0x5102030451020304),
                str(0x5102030451020304),
                str(0x5102030451020304),
                str(0x5102030451020304),
            ],
        ),
        (
            {
                CONF_VIRTUAL_COUNT: 4,
                CONF_DATA_TYPE: DataType.UINT64,
                CONF_UNIQUE_ID: SLAVE_UNIQUE_ID,
                CONF_REGISTER_SIZE_BYTES: 8,
            },
            [
                0x5102030451020304,
                0x5102030451020304,
                0x5102030451020304,
                0x5102030451020304,
                0x5102030451020304,
            ],
            False,
            [
                str(0x5102030451020304),
                str(0x5102030451020304),
                str(0x5102030451020304),
                str(0x5102030451020304),
                str(0x5102030451020304),
            ],
        ),
        (
            {
                CONF_SLAVE_COUNT: 0,
                CONF_UNIQUE_ID: SLAVE_UNIQUE_ID,
                CONF_DATA_TYPE: DataType.FLOAT32,
                CONF_REGISTER_SIZE_BYTES: 4,
                CONF_SCALE: 1,
                CONF_OFFSET: 0,
                CONF_PRECISION: 5,
            },
            [0x3F9E0610],
            False,
            ["1.23456"],
        ),
        (
            {
                CONF_SLAVE_COUNT: 0,
                CONF_UNIQUE_ID: SLAVE_UNIQUE_ID,
                CONF_DATA_TYPE: DataType.INT64,
                CONF_REGISTER_SIZE_BYTES: 4,
            },
            [0x00000000, 0x4129109A],
            False,
            [str(0x000000004129109A)],
        ),
        (
            {
                CONF_SLAVE_COUNT: 0,
                CONF_UNIQUE_ID: SLAVE_UNIQUE_ID,
                CONF_DATA_TYPE: DataType.UINT64,
                CONF_REGISTER_SIZE_BYTES: 8,
            },
            [0x0000000001020304],
            False,
            [str(0x0000000001020304)],
        ),
        (
            {
                CONF_SLAVE_COUNT: 1,
                CONF_UNIQUE_ID: SLAVE_UNIQUE_ID,
                CONF_DATA_TYPE: DataType.UINT32,
                CONF_REGISTER_SIZE_BYTES: 4,
            },
            [0x01020304, 0x04030201],
            True,
            [STATE_UNAVAILABLE, STATE_UNKNOWN],
        ),
        (
            {
                CONF_VIRTUAL_COUNT: 1,
                CONF_UNIQUE_ID: SLAVE_UNIQUE_ID,
                CONF_DATA_TYPE: DataType.UINT32,
                CONF_REGISTER_SIZE_BYTES: 4,
            },
            [0x01020304, 0x04030201],
            True,
            [STATE_UNAVAILABLE, STATE_UNKNOWN],
        ),
    ],
)
async def test_virtual_sensors_with_register_size_not_two_bytes(
    hass: HomeAssistant, mock_do_cycle, expected
) -> None:
    """Run test for virtual sensor with register size."""
    entity_registry = er.async_get(hass)
    for i in range(0, len(expected)):
        entity_id = f"{SENSOR_DOMAIN}.{TEST_ENTITY_NAME}".replace(" ", "_")
        unique_id = f"{SLAVE_UNIQUE_ID}"
        if i:
            entity_id = f"{entity_id}_{i}"
            unique_id = f"{unique_id}_{i}"
        entry = entity_registry.async_get(entity_id)
        state = hass.states.get(entity_id).state
        assert state == expected[i]
        assert entry.unique_id == unique_id


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                },
            ],
        },
    ],
)
@pytest.mark.parametrize(
    ("config_addon", "register_words", "do_exception", "expected"),
    [
        (
            {
                CONF_DATA_TYPE: DataType.FLOAT32,
                CONF_UNIQUE_ID: SLAVE_UNIQUE_ID,
                CONF_REGISTER_SIZE_BYTES: 4,
                CONF_SCALE: 0.001,
                CONF_OFFSET: 2,
                CONF_PRECISION: 4,
            },
            [0x51020304],
            False,
            "34899773.3920",
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT32,
                CONF_ZERO_SUPPRESS: 0x00000001,
                CONF_REGISTER_SIZE_BYTES: 4,
            },
            [0x00000002],
            False,
            str(0x00000002),
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT32,
                CONF_ZERO_SUPPRESS: 0x00000002,
                CONF_REGISTER_SIZE_BYTES: 4,
            },
            [0x00000002],
            False,
            str(0),
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT64,
                CONF_ZERO_SUPPRESS: 0x00000002,
                CONF_REGISTER_SIZE_BYTES: 4,
            },
            [0x00000000, 0x00000002],
            False,
            str(0),
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT64,
                CONF_ZERO_SUPPRESS: 0x00000002,
                CONF_REGISTER_SIZE_BYTES: 8,
            },
            [0x0000000000000002],
            False,
            str(0),
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT64,
                CONF_REGISTER_SIZE_BYTES: 4,
                CONF_MAX_VALUE: 0x02010400,
            },
            [0x02010403, 0x02010403],
            False,
            str(0x02010400),
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT64,
                CONF_REGISTER_SIZE_BYTES: 8,
                CONF_MAX_VALUE: 0x02010400,
            },
            [0x0201040302010403],
            False,
            str(0x02010400),
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT32,
                CONF_REGISTER_SIZE_BYTES: 4,
                CONF_MIN_VALUE: 0x02010404,
            },
            [0x02010403],
            False,
            str(0x02010404),
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT32,
                CONF_NAN_VALUE: "0x80000000",
                CONF_REGISTER_SIZE_BYTES: 4,
            },
            [0x80000000],
            False,
            STATE_UNAVAILABLE,
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT64,
                CONF_NAN_VALUE: "0x80000000",
                CONF_REGISTER_SIZE_BYTES: 4,
            },
            [0x00000000, 0x80000000],
            False,
            STATE_UNAVAILABLE,
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT64,
                CONF_NAN_VALUE: "0x80000000",
                CONF_REGISTER_SIZE_BYTES: 4,
                CONF_SWAP: CONF_SWAP_WORD,
            },
            [0x80000000, 0x00000000],
            False,
            STATE_UNAVAILABLE,
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT64,
                CONF_NAN_VALUE: "0x80000000",
                CONF_REGISTER_SIZE_BYTES: 8,
            },
            [0x0000000080000000],
            False,
            STATE_UNAVAILABLE,
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT32,
                CONF_ZERO_SUPPRESS: 0x00000001,
                CONF_REGISTER_SIZE_BYTES: 4,
            },
            [0x00000002],
            False,
            str(0x00000002),
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT32,
                CONF_ZERO_SUPPRESS: 0x00000002,
                CONF_REGISTER_SIZE_BYTES: 4,
            },
            [0x00000002],
            False,
            str(0),
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT64,
                CONF_ZERO_SUPPRESS: 0x00000002,
                CONF_REGISTER_SIZE_BYTES: 4,
            },
            [0x00000000, 0x00000002],
            False,
            str(0),
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT64,
                CONF_ZERO_SUPPRESS: 0x00000002,
                CONF_REGISTER_SIZE_BYTES: 8,
            },
            [0x0000000000000002],
            False,
            str(0),
        ),
    ],
)
async def test_processing_raw_value_with_register_size_not_two_bytes(
    hass: HomeAssistant, mock_do_cycle, expected
) -> None:
    """Run test for processing sensor value."""
    assert hass.states.get(ENTITY_ID).state == expected
