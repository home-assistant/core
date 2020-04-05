"""The tests for the Modbus sensor component."""
import logging

from homeassistant.components.modbus.const import (
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CONF_COUNT,
    CONF_DATA_TYPE,
    CONF_OFFSET,
    CONF_PRECISION,
    CONF_REGISTER_TYPE,
    CONF_REVERSE_ORDER,
    CONF_SCALE,
    DATA_TYPE_FLOAT,
    DATA_TYPE_INT,
    DATA_TYPE_UINT,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN

from .conftest import run_test

_LOGGER = logging.getLogger(__name__)


async def test_simple_word_register(hass, mock_hub):
    """Test conversion of single word register."""
    register_config = {
        CONF_COUNT: 1,
        CONF_DATA_TYPE: DATA_TYPE_INT,
        CONF_SCALE: 1,
        CONF_OFFSET: 0,
        CONF_PRECISION: 0,
    }
    await run_test(
        hass,
        mock_hub,
        register_config,
        SENSOR_DOMAIN,
        register_words=[0],
        expected="0",
    )


async def test_optional_conf_keys(hass, mock_hub):
    """Test handling of optional configuration keys."""
    register_config = {}
    await run_test(
        hass,
        mock_hub,
        register_config,
        SENSOR_DOMAIN,
        register_words=[0x8000],
        expected="-32768",
    )


async def test_offset(hass, mock_hub):
    """Test offset calculation."""
    register_config = {
        CONF_COUNT: 1,
        CONF_DATA_TYPE: DATA_TYPE_INT,
        CONF_SCALE: 1,
        CONF_OFFSET: 13,
        CONF_PRECISION: 0,
    }
    await run_test(
        hass,
        mock_hub,
        register_config,
        SENSOR_DOMAIN,
        register_words=[7],
        expected="20",
    )


async def test_scale_and_offset(hass, mock_hub):
    """Test handling of scale and offset."""
    register_config = {
        CONF_COUNT: 1,
        CONF_DATA_TYPE: DATA_TYPE_INT,
        CONF_SCALE: 3,
        CONF_OFFSET: 13,
        CONF_PRECISION: 0,
    }
    await run_test(
        hass,
        mock_hub,
        register_config,
        SENSOR_DOMAIN,
        register_words=[7],
        expected="34",
    )


async def test_ints_can_have_precision(hass, mock_hub):
    """Test precision can be specified event if using integer values only."""
    register_config = {
        CONF_COUNT: 1,
        CONF_DATA_TYPE: DATA_TYPE_UINT,
        CONF_SCALE: 3,
        CONF_OFFSET: 13,
        CONF_PRECISION: 4,
    }
    await run_test(
        hass,
        mock_hub,
        register_config,
        SENSOR_DOMAIN,
        register_words=[7],
        expected="34.0000",
    )


async def test_floats_get_rounded_correctly(hass, mock_hub):
    """Test that floating point values get rounded correctly."""
    register_config = {
        CONF_COUNT: 1,
        CONF_DATA_TYPE: DATA_TYPE_INT,
        CONF_SCALE: 1.5,
        CONF_OFFSET: 0,
        CONF_PRECISION: 0,
    }
    await run_test(
        hass,
        mock_hub,
        register_config,
        SENSOR_DOMAIN,
        register_words=[1],
        expected="2",
    )


async def test_parameters_as_strings(hass, mock_hub):
    """Test that scale, offset and precision can be given as strings."""
    register_config = {
        CONF_COUNT: 1,
        CONF_DATA_TYPE: DATA_TYPE_INT,
        CONF_SCALE: "1.5",
        CONF_OFFSET: "5",
        CONF_PRECISION: "1",
    }
    await run_test(
        hass,
        mock_hub,
        register_config,
        SENSOR_DOMAIN,
        register_words=[9],
        expected="18.5",
    )


async def test_floating_point_scale(hass, mock_hub):
    """Test use of floating point scale."""
    register_config = {
        CONF_COUNT: 1,
        CONF_DATA_TYPE: DATA_TYPE_INT,
        CONF_SCALE: 2.4,
        CONF_OFFSET: 0,
        CONF_PRECISION: 2,
    }
    await run_test(
        hass,
        mock_hub,
        register_config,
        SENSOR_DOMAIN,
        register_words=[1],
        expected="2.40",
    )


async def test_floating_point_offset(hass, mock_hub):
    """Test use of floating point scale."""
    register_config = {
        CONF_COUNT: 1,
        CONF_DATA_TYPE: DATA_TYPE_INT,
        CONF_SCALE: 1,
        CONF_OFFSET: -10.3,
        CONF_PRECISION: 1,
    }
    await run_test(
        hass,
        mock_hub,
        register_config,
        SENSOR_DOMAIN,
        register_words=[2],
        expected="-8.3",
    )


async def test_signed_two_word_register(hass, mock_hub):
    """Test reading of signed register with two words."""
    register_config = {
        CONF_COUNT: 2,
        CONF_DATA_TYPE: DATA_TYPE_INT,
        CONF_SCALE: 1,
        CONF_OFFSET: 0,
        CONF_PRECISION: 0,
    }
    await run_test(
        hass,
        mock_hub,
        register_config,
        SENSOR_DOMAIN,
        register_words=[0x89AB, 0xCDEF],
        expected="-1985229329",
    )


async def test_unsigned_two_word_register(hass, mock_hub):
    """Test reading of unsigned register with two words."""
    register_config = {
        CONF_COUNT: 2,
        CONF_DATA_TYPE: DATA_TYPE_UINT,
        CONF_SCALE: 1,
        CONF_OFFSET: 0,
        CONF_PRECISION: 0,
    }
    await run_test(
        hass,
        mock_hub,
        register_config,
        SENSOR_DOMAIN,
        register_words=[0x89AB, 0xCDEF],
        expected=str(0x89ABCDEF),
    )


async def test_reversed(hass, mock_hub):
    """Test handling of reversed register words."""
    register_config = {
        CONF_COUNT: 2,
        CONF_DATA_TYPE: DATA_TYPE_UINT,
        CONF_REVERSE_ORDER: True,
    }
    await run_test(
        hass,
        mock_hub,
        register_config,
        SENSOR_DOMAIN,
        register_words=[0x89AB, 0xCDEF],
        expected=str(0xCDEF89AB),
    )


async def test_four_word_register(hass, mock_hub):
    """Test reading of 64-bit register."""
    register_config = {
        CONF_COUNT: 4,
        CONF_DATA_TYPE: DATA_TYPE_UINT,
        CONF_SCALE: 1,
        CONF_OFFSET: 0,
        CONF_PRECISION: 0,
    }
    await run_test(
        hass,
        mock_hub,
        register_config,
        SENSOR_DOMAIN,
        register_words=[0x89AB, 0xCDEF, 0x0123, 0x4567],
        expected="9920249030613615975",
    )


async def test_four_word_register_precision_is_intact_with_int_params(hass, mock_hub):
    """Test that precision is not lost when doing integer arithmetic for 64-bit register."""
    register_config = {
        CONF_COUNT: 4,
        CONF_DATA_TYPE: DATA_TYPE_UINT,
        CONF_SCALE: 2,
        CONF_OFFSET: 3,
        CONF_PRECISION: 0,
    }
    await run_test(
        hass,
        mock_hub,
        register_config,
        SENSOR_DOMAIN,
        register_words=[0x0123, 0x4567, 0x89AB, 0xCDEF],
        expected="163971058432973793",
    )


async def test_four_word_register_precision_is_lost_with_float_params(hass, mock_hub):
    """Test that precision is affected when floating point conversion is done."""
    register_config = {
        CONF_COUNT: 4,
        CONF_DATA_TYPE: DATA_TYPE_UINT,
        CONF_SCALE: 2.0,
        CONF_OFFSET: 3.0,
        CONF_PRECISION: 0,
    }
    await run_test(
        hass,
        mock_hub,
        register_config,
        SENSOR_DOMAIN,
        register_words=[0x0123, 0x4567, 0x89AB, 0xCDEF],
        expected="163971058432973792",
    )


async def test_two_word_input_register(hass, mock_hub):
    """Test reaging of input register."""
    register_config = {
        CONF_COUNT: 2,
        CONF_REGISTER_TYPE: CALL_TYPE_REGISTER_INPUT,
        CONF_DATA_TYPE: DATA_TYPE_UINT,
        CONF_SCALE: 1,
        CONF_OFFSET: 0,
        CONF_PRECISION: 0,
    }
    await run_test(
        hass,
        mock_hub,
        register_config,
        SENSOR_DOMAIN,
        register_words=[0x89AB, 0xCDEF],
        expected=str(0x89ABCDEF),
    )


async def test_two_word_holding_register(hass, mock_hub):
    """Test reaging of holding register."""
    register_config = {
        CONF_COUNT: 2,
        CONF_REGISTER_TYPE: CALL_TYPE_REGISTER_HOLDING,
        CONF_DATA_TYPE: DATA_TYPE_UINT,
        CONF_SCALE: 1,
        CONF_OFFSET: 0,
        CONF_PRECISION: 0,
    }
    await run_test(
        hass,
        mock_hub,
        register_config,
        SENSOR_DOMAIN,
        register_words=[0x89AB, 0xCDEF],
        expected=str(0x89ABCDEF),
    )


async def test_float_data_type(hass, mock_hub):
    """Test floating point register data type."""
    register_config = {
        CONF_COUNT: 2,
        CONF_REGISTER_TYPE: CALL_TYPE_REGISTER_HOLDING,
        CONF_DATA_TYPE: DATA_TYPE_FLOAT,
        CONF_SCALE: 1,
        CONF_OFFSET: 0,
        CONF_PRECISION: 5,
    }
    await run_test(
        hass,
        mock_hub,
        register_config,
        SENSOR_DOMAIN,
        register_words=[16286, 1617],
        expected="1.23457",
    )
