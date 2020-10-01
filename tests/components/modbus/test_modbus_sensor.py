"""The tests for the Modbus sensor component."""
from datetime import timedelta
import logging

from homeassistant.components.modbus.const import (
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CONF_COUNT,
    CONF_DATA_TYPE,
    CONF_OFFSET,
    CONF_PRECISION,
    CONF_REGISTER,
    CONF_REGISTER_TYPE,
    CONF_REGISTERS,
    CONF_REVERSE_ORDER,
    CONF_SCALE,
    DATA_TYPE_FLOAT,
    DATA_TYPE_INT,
    DATA_TYPE_STRING,
    DATA_TYPE_UINT,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_NAME

from .conftest import run_base_read_test, setup_base_test

_LOGGER = logging.getLogger(__name__)


async def run_sensor_test(
    hass, use_mock_hub, register_config, register_words, expected
):
    """Run test for sensor."""
    sensor_name = "modbus_test_sensor"
    scan_interval = 5
    entity_id, now, device = await setup_base_test(
        sensor_name,
        hass,
        use_mock_hub,
        {
            CONF_REGISTERS: [
                dict(**{CONF_NAME: sensor_name, CONF_REGISTER: 1234}, **register_config)
            ]
        },
        SENSOR_DOMAIN,
        scan_interval,
    )
    await run_base_read_test(
        entity_id,
        hass,
        use_mock_hub,
        register_config.get(CONF_REGISTER_TYPE),
        register_words,
        expected,
        now + timedelta(seconds=scan_interval + 1),
    )


async def test_simple_word_register(hass, mock_hub):
    """Test conversion of single word register."""
    await run_sensor_test(
        hass,
        mock_hub,
        {
            CONF_COUNT: 1,
            CONF_DATA_TYPE: DATA_TYPE_INT,
            CONF_SCALE: 1,
            CONF_OFFSET: 0,
            CONF_PRECISION: 0,
        },
        [0],
        "0",
    )


async def test_optional_conf_keys(hass, mock_hub):
    """Test handling of optional configuration keys."""
    await run_sensor_test(
        hass,
        mock_hub,
        {},
        [0x8000],
        "-32768",
    )


async def test_offset(hass, mock_hub):
    """Test offset calculation."""
    await run_sensor_test(
        hass,
        mock_hub,
        {
            CONF_COUNT: 1,
            CONF_DATA_TYPE: DATA_TYPE_INT,
            CONF_SCALE: 1,
            CONF_OFFSET: 13,
            CONF_PRECISION: 0,
        },
        [7],
        "20",
    )


async def test_scale_and_offset(hass, mock_hub):
    """Test handling of scale and offset."""
    await run_sensor_test(
        hass,
        mock_hub,
        {
            CONF_COUNT: 1,
            CONF_DATA_TYPE: DATA_TYPE_INT,
            CONF_SCALE: 3,
            CONF_OFFSET: 13,
            CONF_PRECISION: 0,
        },
        [7],
        "34",
    )


async def test_ints_can_have_precision(hass, mock_hub):
    """Test precision can be specified event if using integer values only."""
    await run_sensor_test(
        hass,
        mock_hub,
        {
            CONF_COUNT: 1,
            CONF_DATA_TYPE: DATA_TYPE_UINT,
            CONF_SCALE: 3,
            CONF_OFFSET: 13,
            CONF_PRECISION: 4,
        },
        [7],
        "34.0000",
    )


async def test_floats_get_rounded_correctly(hass, mock_hub):
    """Test that floating point values get rounded correctly."""
    await run_sensor_test(
        hass,
        mock_hub,
        {
            CONF_COUNT: 1,
            CONF_DATA_TYPE: DATA_TYPE_INT,
            CONF_SCALE: 1.5,
            CONF_OFFSET: 0,
            CONF_PRECISION: 0,
        },
        [1],
        "2",
    )


async def test_parameters_as_strings(hass, mock_hub):
    """Test that scale, offset and precision can be given as strings."""
    await run_sensor_test(
        hass,
        mock_hub,
        {
            CONF_COUNT: 1,
            CONF_DATA_TYPE: DATA_TYPE_INT,
            CONF_SCALE: "1.5",
            CONF_OFFSET: "5",
            CONF_PRECISION: "1",
        },
        [9],
        "18.5",
    )


async def test_floating_point_scale(hass, mock_hub):
    """Test use of floating point scale."""
    await run_sensor_test(
        hass,
        mock_hub,
        {
            CONF_COUNT: 1,
            CONF_DATA_TYPE: DATA_TYPE_INT,
            CONF_SCALE: 2.4,
            CONF_OFFSET: 0,
            CONF_PRECISION: 2,
        },
        [1],
        "2.40",
    )


async def test_floating_point_offset(hass, mock_hub):
    """Test use of floating point scale."""
    await run_sensor_test(
        hass,
        mock_hub,
        {
            CONF_COUNT: 1,
            CONF_DATA_TYPE: DATA_TYPE_INT,
            CONF_SCALE: 1,
            CONF_OFFSET: -10.3,
            CONF_PRECISION: 1,
        },
        [2],
        "-8.3",
    )


async def test_signed_two_word_register(hass, mock_hub):
    """Test reading of signed register with two words."""
    await run_sensor_test(
        hass,
        mock_hub,
        {
            CONF_COUNT: 2,
            CONF_DATA_TYPE: DATA_TYPE_INT,
            CONF_SCALE: 1,
            CONF_OFFSET: 0,
            CONF_PRECISION: 0,
        },
        [0x89AB, 0xCDEF],
        "-1985229329",
    )


async def test_unsigned_two_word_register(hass, mock_hub):
    """Test reading of unsigned register with two words."""
    await run_sensor_test(
        hass,
        mock_hub,
        {
            CONF_COUNT: 2,
            CONF_DATA_TYPE: DATA_TYPE_UINT,
            CONF_SCALE: 1,
            CONF_OFFSET: 0,
            CONF_PRECISION: 0,
        },
        [0x89AB, 0xCDEF],
        str(0x89ABCDEF),
    )


async def test_reversed(hass, mock_hub):
    """Test handling of reversed register words."""
    await run_sensor_test(
        hass,
        mock_hub,
        {
            CONF_COUNT: 2,
            CONF_DATA_TYPE: DATA_TYPE_UINT,
            CONF_REVERSE_ORDER: True,
        },
        [0x89AB, 0xCDEF],
        str(0xCDEF89AB),
    )


async def test_four_word_register(hass, mock_hub):
    """Test reading of 64-bit register."""
    await run_sensor_test(
        hass,
        mock_hub,
        {
            CONF_COUNT: 4,
            CONF_DATA_TYPE: DATA_TYPE_UINT,
            CONF_SCALE: 1,
            CONF_OFFSET: 0,
            CONF_PRECISION: 0,
        },
        [0x89AB, 0xCDEF, 0x0123, 0x4567],
        "9920249030613615975",
    )


async def test_four_word_register_precision_is_intact_with_int_params(hass, mock_hub):
    """Test that precision is not lost when doing integer arithmetic for 64-bit register."""
    await run_sensor_test(
        hass,
        mock_hub,
        {
            CONF_COUNT: 4,
            CONF_DATA_TYPE: DATA_TYPE_UINT,
            CONF_SCALE: 2,
            CONF_OFFSET: 3,
            CONF_PRECISION: 0,
        },
        [0x0123, 0x4567, 0x89AB, 0xCDEF],
        "163971058432973793",
    )


async def test_four_word_register_precision_is_lost_with_float_params(hass, mock_hub):
    """Test that precision is affected when floating point conversion is done."""
    await run_sensor_test(
        hass,
        mock_hub,
        {
            CONF_COUNT: 4,
            CONF_DATA_TYPE: DATA_TYPE_UINT,
            CONF_SCALE: 2.0,
            CONF_OFFSET: 3.0,
            CONF_PRECISION: 0,
        },
        [0x0123, 0x4567, 0x89AB, 0xCDEF],
        "163971058432973792",
    )


async def test_two_word_input_register(hass, mock_hub):
    """Test reaging of input register."""
    await run_sensor_test(
        hass,
        mock_hub,
        {
            CONF_COUNT: 2,
            CONF_REGISTER_TYPE: CALL_TYPE_REGISTER_INPUT,
            CONF_DATA_TYPE: DATA_TYPE_UINT,
            CONF_SCALE: 1,
            CONF_OFFSET: 0,
            CONF_PRECISION: 0,
        },
        [0x89AB, 0xCDEF],
        str(0x89ABCDEF),
    )


async def test_two_word_holding_register(hass, mock_hub):
    """Test reaging of holding register."""
    await run_sensor_test(
        hass,
        mock_hub,
        {
            CONF_COUNT: 2,
            CONF_REGISTER_TYPE: CALL_TYPE_REGISTER_HOLDING,
            CONF_DATA_TYPE: DATA_TYPE_UINT,
            CONF_SCALE: 1,
            CONF_OFFSET: 0,
            CONF_PRECISION: 0,
        },
        [0x89AB, 0xCDEF],
        str(0x89ABCDEF),
    )


async def test_float_data_type(hass, mock_hub):
    """Test floating point register data type."""
    await run_sensor_test(
        hass,
        mock_hub,
        {
            CONF_COUNT: 2,
            CONF_REGISTER_TYPE: CALL_TYPE_REGISTER_HOLDING,
            CONF_DATA_TYPE: DATA_TYPE_FLOAT,
            CONF_SCALE: 1,
            CONF_OFFSET: 0,
            CONF_PRECISION: 5,
        },
        [16286, 1617],
        "1.23457",
    )


async def test_string_data_type(hass, mock_hub):
    """Test byte string register data type."""
    await run_sensor_test(
        hass,
        mock_hub,
        {
            CONF_COUNT: 8,
            CONF_REGISTER_TYPE: CALL_TYPE_REGISTER_HOLDING,
            CONF_DATA_TYPE: DATA_TYPE_STRING,
            CONF_SCALE: 1,
            CONF_OFFSET: 0,
            CONF_PRECISION: 0,
        },
        [0x3037, 0x2D30, 0x352D, 0x3230, 0x3230, 0x2031, 0x343A, 0x3335],
        "07-05-2020 14:35",
    )
