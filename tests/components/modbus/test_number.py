"""The tests for the Modbus number component."""

from datetime import timedelta
import struct
from unittest import mock

from freezegun.api import FrozenDateTimeFactory
from pymodbus.exceptions import ModbusException
import pytest

from homeassistant.components.homeassistant import SERVICE_UPDATE_ENTITY
from homeassistant.components.modbus.const import (
    CALL_TYPE_REGISTER_HOLDING,
    CONF_DATA_TYPE,
    CONF_DEVICE_ADDRESS,
    CONF_INPUT_TYPE,
    CONF_MAX_VALUE,
    CONF_MIN_VALUE,
    CONF_NUMBER_STEP,
    CONF_NUMBERS,
    CONF_PRECISION,
    CONF_SCALE,
    CONF_SWAP,
    CONF_SWAP_BYTE,
    CONF_SWAP_WORD,
    CONF_SWAP_WORD_BYTE,
    DOMAIN,
    TCP,
    DataType,
)
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ADDRESS,
    CONF_COUNT,
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_NAME,
    CONF_OFFSET,
    CONF_PLATFORM,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    CONF_STRUCTURE,
    CONF_TYPE,
    CONF_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, State
from homeassistant.setup import async_setup_component

from .conftest import (
    TEST_ENTITY_NAME,
    TEST_MODBUS_HOST,
    TEST_MODBUS_NAME,
    TEST_PORT_TCP,
    ReadResult,
)

from tests.common import async_fire_time_changed, mock_restore_cache_with_extra_data

ENTITY_ID = f"{NUMBER_DOMAIN}.{TEST_ENTITY_NAME}".replace(" ", "_")


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_NUMBERS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_DATA_TYPE: DataType.INT16,
                }
            ]
        },
        {
            CONF_NUMBERS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_SLAVE: 10,
                    CONF_DATA_TYPE: DataType.INT16,
                    CONF_PRECISION: 0,
                    CONF_SCALE: 1,
                    CONF_OFFSET: 0,
                    CONF_INPUT_TYPE: CALL_TYPE_REGISTER_HOLDING,
                    CONF_DEVICE_CLASS: "temperature",
                    CONF_UNIT_OF_MEASUREMENT: "°C",
                    CONF_MIN_VALUE: 0,
                    CONF_MAX_VALUE: 100,
                    CONF_NUMBER_STEP: 1,
                }
            ]
        },
        {
            CONF_NUMBERS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_DEVICE_ADDRESS: 10,
                    CONF_DATA_TYPE: DataType.INT16,
                    CONF_PRECISION: 0,
                    CONF_SCALE: 1,
                    CONF_OFFSET: 0,
                    CONF_INPUT_TYPE: CALL_TYPE_REGISTER_HOLDING,
                }
            ]
        },
    ],
)
async def test_config_number(hass: HomeAssistant, mock_modbus: mock.AsyncMock) -> None:
    """Run configuration test for number."""
    assert NUMBER_DOMAIN in hass.config.components


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_NUMBERS: [
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
                CONF_DATA_TYPE: DataType.INT16,
                CONF_SCALE: 2.4,
                CONF_OFFSET: 0,
                CONF_PRECISION: 2,
            },
            [1],
            False,
            "2.4",
        ),
        (
            {
                CONF_DATA_TYPE: DataType.FLOAT32,
                CONF_PRECISION: 2,
            },
            [16286, 1617],
            False,
            "1.23",
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT32,
                CONF_SCALE: 10,
                CONF_OFFSET: 0,
                CONF_PRECISION: 0,
            },
            [0x00AB, 0xCDEF],
            False,
            "112593750",
        ),
        (
            {},
            [0x000A],
            True,
            STATE_UNAVAILABLE,
        ),
    ],
)
async def test_all_number(
    hass: HomeAssistant, mock_do_cycle: FrozenDateTimeFactory, expected: str
) -> None:
    """Run test for number."""
    assert hass.states.get(ENTITY_ID).state == expected


@pytest.mark.parametrize(
    ("value", "register_words", "do_config"),
    [
        (
            31,
            [31],
            {
                CONF_NUMBERS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 51,
                        CONF_SLAVE: 10,
                        CONF_DATA_TYPE: DataType.INT16,
                    }
                ]
            },
        ),
        (
            32,
            struct.unpack(">HH", struct.pack(">i", 32)),
            {
                CONF_NUMBERS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 51,
                        CONF_SLAVE: 10,
                        CONF_DATA_TYPE: DataType.INT32,
                    }
                ]
            },
        ),
        (
            33.5,
            struct.unpack(">HH", struct.pack(">f", 33.5)),
            {
                CONF_NUMBERS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 51,
                        CONF_SLAVE: 10,
                        CONF_DATA_TYPE: DataType.FLOAT32,
                    }
                ]
            },
        ),
        (
            # raw = (value - offset) / scale = (25.0 - 5) / 0.1 = 200
            25.0,
            [200],
            {
                CONF_NUMBERS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 51,
                        CONF_SLAVE: 10,
                        CONF_DATA_TYPE: DataType.INT16,
                        CONF_SCALE: 0.1,
                        CONF_OFFSET: 5,
                    }
                ]
            },
        ),
        (
            # unswapped registers would be struct.unpack(">HH", struct.pack(">i", 32)) = (0, 32);
            # word swap reverses that order before writing.
            32,
            list(reversed(struct.unpack(">HH", struct.pack(">i", 32)))),
            {
                CONF_NUMBERS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 51,
                        CONF_SLAVE: 10,
                        CONF_DATA_TYPE: DataType.INT32,
                        CONF_SWAP: CONF_SWAP_WORD,
                    }
                ]
            },
        ),
    ],
)
async def test_service_number_set_value(
    hass: HomeAssistant,
    value: float,
    register_words: list[int],
    mock_modbus_ha: mock.AsyncMock,
) -> None:
    """Test set_value."""
    mock_modbus_ha.reset_mock()
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_VALUE: value,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    if len(register_words) == 1:
        mock_modbus_ha.write_register.assert_called_with(
            51, value=register_words[0], device_id=10
        )
    else:
        mock_modbus_ha.write_registers.assert_called_with(
            51, values=list(register_words), device_id=10
        )


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_NUMBERS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                },
            ],
        },
    ],
)
async def test_service_number_set_value_write_fails(
    hass: HomeAssistant, mock_modbus_ha: mock.AsyncMock
) -> None:
    """Test set_value when the Modbus write fails."""
    mock_modbus_ha.write_register.side_effect = ModbusException("fail write_")
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_VALUE: 31,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_NUMBERS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
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
                CONF_DATA_TYPE: DataType.INT32,
                CONF_SWAP: CONF_SWAP_BYTE,
            },
            [0x0102, 0x0304],
            str(0x02010403),
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT32,
                CONF_SWAP: CONF_SWAP_WORD,
            },
            [0x0102, 0x0304],
            str(0x03040102),
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT32,
                CONF_SWAP: CONF_SWAP_WORD_BYTE,
            },
            [0x0102, 0x0304],
            str(0x04030201),
        ),
    ],
)
async def test_swap_number_read(
    hass: HomeAssistant,
    mock_do_cycle: FrozenDateTimeFactory,
    register_words: list[int],
    expected: str,
) -> None:
    """Run test for number with swap on read."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == expected


@pytest.fixture(name="mock_restore")
async def mock_restore(hass: HomeAssistant) -> None:
    """Mock restore cache."""
    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State(ENTITY_ID, "42.5"),
                {
                    "native_value": 42.5,
                    "native_min_value": 0.0,
                    "native_max_value": 100.0,
                    "native_step": 1.0,
                    "native_unit_of_measurement": None,
                },
            ),
        ),
    )


async def test_restore_state_number(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_restore: None,
    mock_pymodbus: mock.AsyncMock,
) -> None:
    """Verify a restored value is shown until the first successful update."""
    config = {
        DOMAIN: [
            {
                CONF_TYPE: TCP,
                CONF_HOST: TEST_MODBUS_HOST,
                CONF_PORT: TEST_PORT_TCP,
                CONF_NAME: TEST_MODBUS_NAME,
                CONF_NUMBERS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 51,
                        CONF_SCAN_INTERVAL: 0,
                    }
                ],
            }
        ]
    }
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    # Before the connection has completed and triggered the first read,
    # the restored value must still be shown.
    assert hass.states.get(ENTITY_ID).state == "42.5"

    # Once the connection is established, the first real read overwrites it.
    freezer.tick(timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "0"


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_NUMBERS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_DATA_TYPE: DataType.INT16,
                }
            ]
        },
    ],
)
async def test_service_number_update(
    hass: HomeAssistant, mock_modbus_ha: mock.AsyncMock
) -> None:
    """Run test for service homeassistant.update_entity."""
    mock_modbus_ha.read_holding_registers.return_value = ReadResult([27])
    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID).state == "27"
    mock_modbus_ha.read_holding_registers.return_value = ReadResult([32])
    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID).state == "32"


async def test_no_discovery_info_number(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setup without discovery info."""
    assert NUMBER_DOMAIN not in hass.config.components
    assert await async_setup_component(
        hass,
        NUMBER_DOMAIN,
        {NUMBER_DOMAIN: {CONF_PLATFORM: DOMAIN}},
    )
    await hass.async_block_till_done()
    assert NUMBER_DOMAIN in hass.config.components


@pytest.mark.parametrize("check_config_loaded", [False])
@pytest.mark.parametrize(
    "do_config",
    [
        pytest.param(
            {
                CONF_NUMBERS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 51,
                        CONF_DATA_TYPE: DataType.INT16,
                        CONF_SCALE: 0,
                    }
                ]
            },
            id="zero_scale",
        ),
        pytest.param(
            {
                CONF_NUMBERS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 51,
                        CONF_DATA_TYPE: DataType.STRING,
                        CONF_COUNT: 2,
                    }
                ]
            },
            id="string_data_type",
        ),
        pytest.param(
            {
                CONF_NUMBERS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 51,
                        CONF_DATA_TYPE: DataType.CUSTOM,
                        CONF_STRUCTURE: ">ff",
                        CONF_COUNT: 2,
                    }
                ]
            },
            id="custom_data_type",
        ),
        pytest.param(
            {
                CONF_NUMBERS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 51,
                        CONF_MIN_VALUE: 100,
                        CONF_MAX_VALUE: 0,
                    }
                ]
            },
            id="min_value_greater_than_max_value",
        ),
        pytest.param(
            {
                CONF_NUMBERS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 51,
                        CONF_NUMBER_STEP: 0,
                    }
                ]
            },
            id="zero_step",
        ),
        pytest.param(
            {
                CONF_NUMBERS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 51,
                        CONF_NUMBER_STEP: -1,
                    }
                ]
            },
            id="negative_step",
        ),
    ],
)
async def test_err_config_number(
    hass: HomeAssistant, mock_modbus: mock.AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Run test for number with wrong config."""
    assert NUMBER_DOMAIN not in hass.config.components
