"""The tests for the Modbus sensor component."""
import pytest

from homeassistant.components.modbus.const import (
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CONF_DATA_TYPE,
    CONF_INPUT_TYPE,
    CONF_LAZY_ERROR,
    CONF_MAX_VALUE,
    CONF_MIN_VALUE,
    CONF_NAN_VALUE,
    CONF_PRECISION,
    CONF_SCALE,
    CONF_SLAVE_COUNT,
    CONF_SWAP,
    CONF_SWAP_BYTE,
    CONF_SWAP_NONE,
    CONF_SWAP_WORD,
    CONF_SWAP_WORD_BYTE,
    CONF_ZERO_SUPPRESS,
    MODBUS_DOMAIN,
    DataType,
)
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    DOMAIN as SENSOR_DOMAIN,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_COUNT,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_OFFSET,
    CONF_SCAN_INTERVAL,
    CONF_SENSORS,
    CONF_SLAVE,
    CONF_STRUCTURE,
    CONF_UNIQUE_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import TEST_ENTITY_NAME, ReadResult, do_next_cycle

from tests.common import mock_restore_cache_with_extra_data

ENTITY_ID = f"{SENSOR_DOMAIN}.{TEST_ENTITY_NAME}".replace(" ", "_")
SLAVE_UNIQUE_ID = "ground_floor_sensor"


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_DATA_TYPE: DataType.INT16,
                }
            ]
        },
        {
            CONF_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_SLAVE: 10,
                    CONF_DATA_TYPE: DataType.INT16,
                    CONF_PRECISION: 0,
                    CONF_SCALE: 1,
                    CONF_OFFSET: 0,
                    CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                    CONF_LAZY_ERROR: 10,
                    CONF_INPUT_TYPE: CALL_TYPE_REGISTER_HOLDING,
                    CONF_DEVICE_CLASS: "battery",
                }
            ]
        },
        {
            CONF_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_SLAVE: 10,
                    CONF_DATA_TYPE: DataType.INT16,
                    CONF_PRECISION: 0,
                    CONF_SCALE: 1,
                    CONF_OFFSET: 0,
                    CONF_INPUT_TYPE: CALL_TYPE_REGISTER_INPUT,
                    CONF_DEVICE_CLASS: "battery",
                }
            ]
        },
        {
            CONF_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_DATA_TYPE: DataType.INT16,
                    CONF_SWAP: CONF_SWAP_NONE,
                }
            ]
        },
        {
            CONF_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_DATA_TYPE: DataType.INT16,
                    CONF_SWAP: CONF_SWAP_BYTE,
                }
            ]
        },
        {
            CONF_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_DATA_TYPE: DataType.INT32,
                    CONF_SWAP: CONF_SWAP_WORD,
                }
            ]
        },
        {
            CONF_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_DATA_TYPE: DataType.INT32,
                    CONF_SWAP: CONF_SWAP_WORD_BYTE,
                }
            ]
        },
        {
            CONF_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_DATA_TYPE: DataType.INT32,
                    CONF_SLAVE_COUNT: 5,
                }
            ]
        },
    ],
)
async def test_config_sensor(hass: HomeAssistant, mock_modbus) -> None:
    """Run configuration test for sensor."""
    assert SENSOR_DOMAIN in hass.config.components


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
                        CONF_COUNT: 8,
                        CONF_PRECISION: 2,
                        CONF_DATA_TYPE: DataType.CUSTOM,
                        CONF_STRUCTURE: ">no struct",
                    },
                ]
            },
            "bad char in struct format",
        ),
        (
            {
                CONF_SENSORS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 1234,
                        CONF_COUNT: 2,
                        CONF_PRECISION: 2,
                        CONF_DATA_TYPE: DataType.CUSTOM,
                        CONF_STRUCTURE: ">4f",
                    },
                ]
            },
            "Structure request 16 bytes, but 2 registers have a size of 4 bytes",
        ),
        (
            {
                CONF_SENSORS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 1234,
                        CONF_DATA_TYPE: DataType.CUSTOM,
                        CONF_COUNT: 4,
                        CONF_SWAP: CONF_SWAP_NONE,
                        CONF_STRUCTURE: "invalid",
                    },
                ]
            },
            "bad char in struct format",
        ),
        (
            {
                CONF_SENSORS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 1234,
                        CONF_DATA_TYPE: DataType.CUSTOM,
                        CONF_COUNT: 4,
                        CONF_SWAP: CONF_SWAP_NONE,
                        CONF_STRUCTURE: "",
                    },
                ]
            },
            f"Error in sensor {TEST_ENTITY_NAME}. The `structure` field cannot be empty",
        ),
        (
            {
                CONF_SENSORS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 1234,
                        CONF_DATA_TYPE: DataType.CUSTOM,
                        CONF_COUNT: 4,
                        CONF_SWAP: CONF_SWAP_NONE,
                        CONF_STRUCTURE: "1s",
                    },
                ]
            },
            "Structure request 1 bytes, but 4 registers have a size of 8 bytes",
        ),
        (
            {
                CONF_SENSORS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 1234,
                        CONF_DATA_TYPE: DataType.CUSTOM,
                        CONF_COUNT: 1,
                        CONF_STRUCTURE: "2s",
                        CONF_SWAP: CONF_SWAP_WORD,
                    },
                ]
            },
            f"Error in sensor {TEST_ENTITY_NAME} swap(word) not possible due to the registers count: 1, needed: 2",
        ),
    ],
)
async def test_config_wrong_struct_sensor(
    hass: HomeAssistant, error_message, mock_modbus, caplog: pytest.LogCaptureFixture
) -> None:
    """Run test for sensor with wrong struct."""
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
                    CONF_SCAN_INTERVAL: 1,
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
                CONF_DATA_TYPE: DataType.INT16,
                CONF_SCALE: 1,
                CONF_OFFSET: 0,
                CONF_PRECISION: 0,
            },
            [0],
            False,
            "0",
        ),
        (
            {},
            [0x8000],
            False,
            "-32768",
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT16,
                CONF_SCALE: 1,
                CONF_OFFSET: 13,
                CONF_PRECISION: 0,
            },
            [7],
            False,
            "20",
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT16,
                CONF_SCALE: 3,
                CONF_OFFSET: 13,
                CONF_PRECISION: 0,
            },
            [7],
            False,
            "34",
        ),
        (
            {
                CONF_DATA_TYPE: DataType.UINT16,
                CONF_SCALE: 3,
                CONF_OFFSET: 13,
                CONF_PRECISION: 4,
            },
            [7],
            False,
            "34.0000",
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT16,
                CONF_SCALE: 1.5,
                CONF_OFFSET: 0,
                CONF_PRECISION: 0,
            },
            [1],
            False,
            "2",
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT16,
                CONF_SCALE: "1.5",
                CONF_OFFSET: "5",
                CONF_PRECISION: "1",
            },
            [9],
            False,
            "18.5",
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT16,
                CONF_SCALE: 2.4,
                CONF_OFFSET: 0,
                CONF_PRECISION: 2,
            },
            [1],
            False,
            "2.40",
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT16,
                CONF_SCALE: 1,
                CONF_OFFSET: -10.3,
                CONF_PRECISION: 1,
            },
            [2],
            False,
            "-8.3",
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT32,
                CONF_SCALE: 1,
                CONF_OFFSET: 0,
                CONF_PRECISION: 0,
            },
            [0x89AB, 0xCDEF],
            False,
            "-1985229329",
        ),
        (
            {
                CONF_DATA_TYPE: DataType.UINT32,
                CONF_SCALE: 1,
                CONF_OFFSET: 0,
                CONF_PRECISION: 0,
            },
            [0x89AB, 0xCDEF],
            False,
            str(0x89ABCDEF),
        ),
        (
            {
                CONF_DATA_TYPE: DataType.UINT64,
                CONF_SCALE: 1,
                CONF_OFFSET: 0,
                CONF_PRECISION: 0,
            },
            [0x89AB, 0xCDEF, 0x0123, 0x4567],
            False,
            "9920249030613615975",
        ),
        (
            {
                CONF_DATA_TYPE: DataType.UINT64,
                CONF_SCALE: 2,
                CONF_OFFSET: 3,
                CONF_PRECISION: 0,
            },
            [0x0123, 0x4567, 0x89AB, 0xCDEF],
            False,
            "163971058432973793",
        ),
        (
            {
                CONF_DATA_TYPE: DataType.UINT64,
                CONF_SCALE: 2.0,
                CONF_OFFSET: 3.0,
                CONF_PRECISION: 0,
            },
            [0x0123, 0x4567, 0x89AB, 0xCDEF],
            False,
            "163971058432973792",
        ),
        (
            {
                CONF_INPUT_TYPE: CALL_TYPE_REGISTER_INPUT,
                CONF_DATA_TYPE: DataType.UINT32,
                CONF_SCALE: 1,
                CONF_OFFSET: 0,
                CONF_PRECISION: 0,
            },
            [0x89AB, 0xCDEF],
            False,
            str(0x89ABCDEF),
        ),
        (
            {
                CONF_INPUT_TYPE: CALL_TYPE_REGISTER_HOLDING,
                CONF_DATA_TYPE: DataType.UINT32,
                CONF_SCALE: 1,
                CONF_OFFSET: 0,
                CONF_PRECISION: 0,
            },
            [0x89AB, 0xCDEF],
            False,
            str(0x89ABCDEF),
        ),
        (
            {
                CONF_INPUT_TYPE: CALL_TYPE_REGISTER_HOLDING,
                CONF_DATA_TYPE: DataType.FLOAT32,
                CONF_SCALE: 1,
                CONF_OFFSET: 0,
                CONF_PRECISION: 5,
            },
            [16286, 1617],
            False,
            "1.23457",
        ),
        (
            {
                CONF_COUNT: 8,
                CONF_INPUT_TYPE: CALL_TYPE_REGISTER_HOLDING,
                CONF_DATA_TYPE: DataType.STRING,
                CONF_SCALE: 1,
                CONF_OFFSET: 0,
                CONF_PRECISION: 0,
            },
            [0x3037, 0x2D30, 0x352D, 0x3230, 0x3230, 0x2031, 0x343A, 0x3335],
            False,
            "07-05-2020 14:35",
        ),
        (
            {
                CONF_COUNT: 8,
                CONF_INPUT_TYPE: CALL_TYPE_REGISTER_HOLDING,
                CONF_DATA_TYPE: DataType.STRING,
                CONF_SCALE: 1,
                CONF_OFFSET: 0,
                CONF_PRECISION: 0,
            },
            [0x00],
            True,
            STATE_UNAVAILABLE,
        ),
        (
            {
                CONF_INPUT_TYPE: CALL_TYPE_REGISTER_INPUT,
                CONF_DATA_TYPE: DataType.UINT32,
                CONF_SCALE: 1,
                CONF_OFFSET: 0,
                CONF_PRECISION: 0,
            },
            [0x00],
            True,
            STATE_UNAVAILABLE,
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT16,
                CONF_SWAP: CONF_SWAP_NONE,
            },
            [0x0102],
            False,
            str(int(0x0102)),
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT16,
                CONF_SWAP: CONF_SWAP_BYTE,
            },
            [0x0201],
            False,
            str(int(0x0102)),
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT32,
                CONF_SWAP: CONF_SWAP_BYTE,
            },
            [0x0102, 0x0304],
            False,
            str(int(0x02010403)),
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT32,
                CONF_SWAP: CONF_SWAP_WORD,
            },
            [0x0102, 0x0304],
            False,
            str(int(0x03040102)),
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT32,
                CONF_SWAP: CONF_SWAP_WORD_BYTE,
            },
            [0x0102, 0x0304],
            False,
            str(int(0x04030201)),
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT32,
                CONF_MAX_VALUE: int(0x02010400),
            },
            [0x0201, 0x0403],
            False,
            str(int(0x02010400)),
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT32,
                CONF_MIN_VALUE: int(0x02010404),
            },
            [0x0201, 0x0403],
            False,
            str(int(0x02010404)),
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT32,
                CONF_NAN_VALUE: "0x80000000",
            },
            [0x8000, 0x0000],
            False,
            STATE_UNAVAILABLE,
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT32,
                CONF_ZERO_SUPPRESS: int(0x00000001),
            },
            [0x0000, 0x0002],
            False,
            str(int(0x00000002)),
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT32,
                CONF_ZERO_SUPPRESS: int(0x00000002),
            },
            [0x0000, 0x0002],
            False,
            str(int(0)),
        ),
        (
            {
                CONF_INPUT_TYPE: CALL_TYPE_REGISTER_INPUT,
                CONF_DATA_TYPE: DataType.FLOAT32,
                CONF_PRECISION: 2,
            },
            [16286, 1617],
            False,
            "1.23",
        ),
    ],
)
async def test_all_sensor(hass: HomeAssistant, mock_do_cycle, expected) -> None:
    """Run test for sensor."""
    assert hass.states.get(ENTITY_ID).state == expected


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_INPUT_TYPE: CALL_TYPE_REGISTER_HOLDING,
                    CONF_DATA_TYPE: DataType.UINT32,
                    CONF_SCALE: 1,
                    CONF_OFFSET: 0,
                    CONF_PRECISION: 0,
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
                CONF_SLAVE_COUNT: 0,
                CONF_UNIQUE_ID: SLAVE_UNIQUE_ID,
            },
            [0x0102, 0x0304],
            False,
            ["16909060"],
        ),
        (
            {
                CONF_SLAVE_COUNT: 1,
                CONF_UNIQUE_ID: SLAVE_UNIQUE_ID,
            },
            [0x0102, 0x0304, 0x0403, 0x0201],
            False,
            ["16909060", "67305985"],
        ),
        (
            {
                CONF_SLAVE_COUNT: 3,
                CONF_UNIQUE_ID: SLAVE_UNIQUE_ID,
            },
            [
                0x0102,
                0x0304,
                0x0506,
                0x0708,
                0x090A,
                0x0B0C,
                0x0D0E,
                0x0F00,
            ],
            False,
            [
                "16909060",
                "84281096",
                "151653132",
                "219025152",
            ],
        ),
        (
            {
                CONF_SLAVE_COUNT: 1,
                CONF_UNIQUE_ID: SLAVE_UNIQUE_ID,
            },
            [0x0102, 0x0304, 0x0403, 0x0201],
            True,
            [STATE_UNAVAILABLE, STATE_UNKNOWN],
        ),
        (
            {
                CONF_SLAVE_COUNT: 1,
                CONF_UNIQUE_ID: SLAVE_UNIQUE_ID,
            },
            [],
            False,
            [STATE_UNAVAILABLE, STATE_UNKNOWN],
        ),
    ],
)
async def test_slave_sensor(hass: HomeAssistant, mock_do_cycle, expected) -> None:
    """Run test for sensor."""
    assert hass.states.get(ENTITY_ID).state == expected[0]
    entity_registry = er.async_get(hass)

    for i in range(1, len(expected)):
        entity_id = f"{SENSOR_DOMAIN}.{TEST_ENTITY_NAME}_{i}".replace(" ", "_")
        assert hass.states.get(entity_id).state == expected[i]
        unique_id = f"{SLAVE_UNIQUE_ID}_{i}"
        entry = entity_registry.async_get(entity_id)
        assert entry.unique_id == unique_id


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_SCAN_INTERVAL: 1,
                },
            ],
        },
    ],
)
@pytest.mark.parametrize(
    ("config_addon", "register_words"),
    [
        (
            {
                CONF_DATA_TYPE: DataType.INT16,
            },
            [7, 9],
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT32,
            },
            [7],
        ),
    ],
)
async def test_wrong_unpack(hass: HomeAssistant, mock_do_cycle) -> None:
    """Run test for sensor."""
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_SCAN_INTERVAL: 10,
                    CONF_LAZY_ERROR: 1,
                },
            ],
        },
    ],
)
@pytest.mark.parametrize(
    ("register_words", "do_exception", "start_expect", "end_expect"),
    [
        (
            [0x8000],
            True,
            "17",
            STATE_UNAVAILABLE,
        ),
    ],
)
async def test_lazy_error_sensor(
    hass: HomeAssistant, mock_do_cycle, start_expect, end_expect
) -> None:
    """Run test for sensor."""
    hass.states.async_set(ENTITY_ID, 17)
    await hass.async_block_till_done()
    now = mock_do_cycle
    assert hass.states.get(ENTITY_ID).state == start_expect
    now = await do_next_cycle(hass, now, 11)
    assert hass.states.get(ENTITY_ID).state == start_expect
    now = await do_next_cycle(hass, now, 11)
    assert hass.states.get(ENTITY_ID).state == end_expect


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_SCAN_INTERVAL: 1,
                },
            ],
        },
    ],
)
@pytest.mark.parametrize(
    ("config_addon", "register_words", "expected"),
    [
        (
            {
                CONF_COUNT: 8,
                CONF_PRECISION: 2,
                CONF_DATA_TYPE: DataType.CUSTOM,
                CONF_STRUCTURE: ">4f",
            },
            # floats: 7.931250095367432, 10.600000381469727,
            #         1.000879611487865e-28, 10.566553115844727
            [0x40FD, 0xCCCD, 0x4129, 0x999A, 0x10FD, 0xC0CD, 0x4129, 0x109A],
            "7.93,10.60,0.00,10.57",
        ),
        (
            {
                CONF_COUNT: 4,
                CONF_PRECISION: 0,
                CONF_DATA_TYPE: DataType.CUSTOM,
                CONF_STRUCTURE: ">2i",
            },
            [0x0000, 0x0100, 0x0000, 0x0032],
            "256,50",
        ),
        (
            {
                CONF_PRECISION: 0,
                CONF_DATA_TYPE: DataType.INT16,
            },
            [0x0101],
            "257",
        ),
    ],
)
async def test_struct_sensor(hass: HomeAssistant, mock_do_cycle, expected) -> None:
    """Run test for sensor struct."""
    assert hass.states.get(ENTITY_ID).state == expected


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 201,
                    CONF_SCAN_INTERVAL: 1,
                },
            ],
        },
    ],
)
@pytest.mark.parametrize(
    ("config_addon", "register_words", "expected"),
    [
        (
            {
                CONF_COUNT: 1,
                CONF_SWAP: CONF_SWAP_NONE,
                CONF_DATA_TYPE: DataType.UINT16,
            },
            [0x0102],
            "258",
        ),
        (
            {
                CONF_COUNT: 1,
                CONF_SWAP: CONF_SWAP_BYTE,
                CONF_DATA_TYPE: DataType.UINT16,
            },
            [0x0102],
            "513",
        ),
        (
            {
                CONF_COUNT: 2,
                CONF_SWAP: CONF_SWAP_NONE,
                CONF_DATA_TYPE: DataType.UINT32,
            },
            [0x0102, 0x0304],
            "16909060",
        ),
        (
            {
                CONF_COUNT: 2,
                CONF_SWAP: CONF_SWAP_BYTE,
                CONF_DATA_TYPE: DataType.UINT32,
            },
            [0x0102, 0x0304],
            "33620995",
        ),
        (
            {
                CONF_COUNT: 2,
                CONF_SWAP: CONF_SWAP_WORD,
                CONF_DATA_TYPE: DataType.UINT32,
            },
            [0x0102, 0x0304],
            "50594050",
        ),
        (
            {
                CONF_COUNT: 2,
                CONF_SWAP: CONF_SWAP_WORD_BYTE,
                CONF_DATA_TYPE: DataType.UINT32,
            },
            [0x0102, 0x0304],
            "67305985",
        ),
    ],
)
async def test_wrap_sensor(hass: HomeAssistant, mock_do_cycle, expected) -> None:
    """Run test for sensor struct."""
    assert hass.states.get(ENTITY_ID).state == expected


@pytest.fixture(name="mock_restore")
async def mock_restore(hass):
    """Mock restore cache."""
    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State(ENTITY_ID, "121"),
                {"native_value": "121", "native_unit_of_measurement": "kg"},
            ),
            (
                State(ENTITY_ID + "_1", "119"),
                {"native_value": "119", "native_unit_of_measurement": "kg"},
            ),
        ),
    )


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_SCAN_INTERVAL: 0,
                    CONF_SLAVE_COUNT: 1,
                }
            ]
        },
    ],
)
async def test_restore_state_sensor(
    hass: HomeAssistant, mock_restore, mock_modbus
) -> None:
    """Run test for sensor restore state."""
    state = hass.states.get(ENTITY_ID).state
    state2 = hass.states.get(ENTITY_ID + "_1").state
    assert state
    assert state2


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 1234,
                    CONF_INPUT_TYPE: CALL_TYPE_REGISTER_INPUT,
                }
            ]
        },
    ],
)
async def test_service_sensor_update(hass: HomeAssistant, mock_modbus, mock_ha) -> None:
    """Run test for service homeassistant.update_entity."""
    mock_modbus.read_input_registers.return_value = ReadResult([27])
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": ENTITY_ID}, blocking=True
    )
    assert hass.states.get(ENTITY_ID).state == "27"
    mock_modbus.read_input_registers.return_value = ReadResult([32])
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": ENTITY_ID}, blocking=True
    )
    assert hass.states.get(ENTITY_ID).state == "32"


async def test_no_discovery_info_sensor(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setup without discovery info."""
    assert SENSOR_DOMAIN not in hass.config.components
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {SENSOR_DOMAIN: {"platform": MODBUS_DOMAIN}},
    )
    await hass.async_block_till_done()
    assert SENSOR_DOMAIN in hass.config.components
