"""The tests for the Modbus sensor component."""

import pytest

from homeassistant.components.modbus.const import (
    CONF_DATA_TYPE,
    CONF_REGISTER_SIZE_BYTES,
    DataType,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_COUNT,
    CONF_NAME,
    CONF_SENSORS,
    CONF_STRUCTURE,
)
from homeassistant.core import HomeAssistant

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
                CONF_DATA_TYPE: DataType.UINT8,
            },
            1,
        ),
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
            "Combination of data type and register size does generate an posivite integer count.",
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
            "Combination of data type and register size does generate an posivite integer count.",
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
            "test entity: `register_size_bytes:10` is out of range. Accepted values are 2, 4 or 8 bytes.",
        ),
    ],
)
async def test_register_bytes_incorrectly_set(
    hass: HomeAssistant, error_message, mock_modbus, caplog: pytest.LogCaptureFixture
) -> None:
    """Run test for sensor with wrong register size in bytes."""
    messages = str([x.message for x in caplog.get_records("setup")])
    assert error_message in messages
