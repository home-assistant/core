"""Test for Melissa climate component."""
from unittest.mock import Mock, patch
import json

from homeassistant.components.melissa.climate import MelissaClimate

from homeassistant.components.melissa import climate as melissa
from homeassistant.components.climate.const import (
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_OPERATION_MODE,
    SUPPORT_ON_OFF, SUPPORT_FAN_MODE, STATE_HEAT, STATE_FAN_ONLY, STATE_DRY,
    STATE_COOL, STATE_AUTO
)
from homeassistant.components.fan import SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH
from homeassistant.components.melissa import DATA_MELISSA
from homeassistant.const import (
    TEMP_CELSIUS, STATE_ON, ATTR_TEMPERATURE, STATE_OFF, STATE_IDLE
)
from tests.common import load_fixture, mock_coro_func

_SERIAL = "12345678"


def melissa_mock():
    """Use this to mock the melissa api."""
    api = Mock()
    api.async_fetch_devices = mock_coro_func(
        return_value=json.loads(load_fixture('melissa_fetch_devices.json')))
    api.async_status = mock_coro_func(return_value=json.loads(load_fixture(
        'melissa_status.json')))
    api.async_cur_settings = mock_coro_func(
        return_value=json.loads(load_fixture('melissa_cur_settings.json')))

    api.async_send = mock_coro_func(return_value=True)

    api.STATE_OFF = 0
    api.STATE_ON = 1
    api.STATE_IDLE = 2

    api.MODE_AUTO = 0
    api.MODE_FAN = 1
    api.MODE_HEAT = 2
    api.MODE_COOL = 3
    api.MODE_DRY = 4

    api.FAN_AUTO = 0
    api.FAN_LOW = 1
    api.FAN_MEDIUM = 2
    api.FAN_HIGH = 3

    api.STATE = 'state'
    api.MODE = 'mode'
    api.FAN = 'fan'
    api.TEMP = 'temp'
    return api


async def test_setup_platform(hass):
    """Test setup_platform."""
    with patch("homeassistant.components.melissa.climate.MelissaClimate"
               ) as mocked_thermostat:
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = mocked_thermostat(api, device['serial_number'],
                                       device)
        thermostats = [thermostat]

        hass.data[DATA_MELISSA] = api

        config = {}
        add_entities = Mock()
        discovery_info = {}

        await melissa.async_setup_platform(
            hass, config, add_entities, discovery_info)
        add_entities.assert_called_once_with(thermostats)


async def test_get_name(hass):
    """Test name property."""
    with patch('homeassistant.components.melissa'):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        assert "Melissa 12345678" == thermostat.name


async def test_is_on(hass):
    """Test name property."""
    with patch('homeassistant.components.melissa'):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        await thermostat.async_update()
        assert thermostat.is_on

        thermostat._cur_settings = None
        assert not thermostat.is_on


async def test_current_fan_mode(hass):
    """Test current_fan_mode property."""
    with patch('homeassistant.components.melissa'):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        await thermostat.async_update()
        assert SPEED_LOW == thermostat.current_fan_mode

        thermostat._cur_settings = None
        assert thermostat.current_fan_mode is None


async def test_current_temperature(hass):
    """Test current temperature."""
    with patch('homeassistant.components.melissa'):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        assert 27.4 == thermostat.current_temperature


async def test_current_temperature_no_data(hass):
    """Test current temperature without data."""
    with patch('homeassistant.components.melissa'):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        thermostat._data = None
        assert thermostat.current_temperature is None


async def test_target_temperature_step(hass):
    """Test current target_temperature_step."""
    with patch('homeassistant.components.melissa'):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        assert 1 == thermostat.target_temperature_step


async def test_current_operation(hass):
    """Test current operation."""
    with patch('homeassistant.components.melissa'):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        await thermostat.async_update()
        assert thermostat.current_operation == STATE_HEAT

        thermostat._cur_settings = None
        assert thermostat.current_operation is None


async def test_operation_list(hass):
    """Test the operation list."""
    with patch('homeassistant.components.melissa'):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        assert [STATE_COOL, STATE_DRY, STATE_FAN_ONLY, STATE_HEAT] == \
            thermostat.operation_list


async def test_fan_list(hass):
    """Test the fan list."""
    with patch('homeassistant.components.melissa'):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        assert [STATE_AUTO, SPEED_HIGH, SPEED_LOW, SPEED_MEDIUM] == \
            thermostat.fan_list


async def test_target_temperature(hass):
    """Test target temperature."""
    with patch('homeassistant.components.melissa'):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        await thermostat.async_update()
        assert 16 == thermostat.target_temperature

        thermostat._cur_settings = None
        assert thermostat.target_temperature is None


async def test_state(hass):
    """Test state."""
    with patch('homeassistant.components.melissa'):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        await thermostat.async_update()
        assert STATE_ON == thermostat.state

        thermostat._cur_settings = None
        assert thermostat.state is None


async def test_temperature_unit(hass):
    """Test temperature unit."""
    with patch('homeassistant.components.melissa'):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        assert TEMP_CELSIUS == thermostat.temperature_unit


async def test_min_temp(hass):
    """Test min temp."""
    with patch('homeassistant.components.melissa'):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        assert 16 == thermostat.min_temp


async def test_max_temp(hass):
    """Test max temp."""
    with patch('homeassistant.components.melissa'):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        assert 30 == thermostat.max_temp


async def test_supported_features(hass):
    """Test supported_features property."""
    with patch('homeassistant.components.melissa'):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        features = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE |
                    SUPPORT_ON_OFF | SUPPORT_FAN_MODE)
        assert features == thermostat.supported_features


async def test_set_temperature(hass):
    """Test set_temperature."""
    with patch('homeassistant.components.melissa'):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        await thermostat.async_update()
        await thermostat.async_set_temperature(**{ATTR_TEMPERATURE: 25})
        assert 25 == thermostat.target_temperature


async def test_fan_mode(hass):
    """Test set_fan_mode."""
    with patch('homeassistant.components.melissa'):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        await thermostat.async_update()
        await hass.async_block_till_done()
        await thermostat.async_set_fan_mode(SPEED_HIGH)
        await hass.async_block_till_done()
        assert SPEED_HIGH == thermostat.current_fan_mode


async def test_set_operation_mode(hass):
    """Test set_operation_mode."""
    with patch('homeassistant.components.melissa'):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        await thermostat.async_update()
        await hass.async_block_till_done()
        await thermostat.async_set_operation_mode(STATE_COOL)
        await hass.async_block_till_done()
        assert STATE_COOL == thermostat.current_operation


async def test_turn_on(hass):
    """Test turn_on."""
    with patch('homeassistant.components.melissa'):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        await thermostat.async_update()
        await hass.async_block_till_done()
        await thermostat.async_turn_on()
        await hass.async_block_till_done()
        assert thermostat.state


async def test_turn_off(hass):
    """Test turn_off."""
    with patch('homeassistant.components.melissa'):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        await thermostat.async_update()
        await hass.async_block_till_done()
        await thermostat.async_turn_off()
        await hass.async_block_till_done()
        assert STATE_OFF == thermostat.state


async def test_send(hass):
    """Test send."""
    with patch('homeassistant.components.melissa'):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        await thermostat.async_update()
        await hass.async_block_till_done()
        await thermostat.async_send({'fan': api.FAN_MEDIUM})
        await hass.async_block_till_done()
        assert SPEED_MEDIUM == thermostat.current_fan_mode
        api.async_send.return_value = mock_coro_func(return_value=False)
        thermostat._cur_settings = None
        await thermostat.async_send({'fan': api.FAN_LOW})
        await hass.async_block_till_done()
        assert SPEED_LOW != thermostat.current_fan_mode
        assert thermostat._cur_settings is None


async def test_update(hass):
    """Test update."""
    with patch('homeassistant.components.melissa.climate._LOGGER.warning'
               ) as mocked_warning:
        with patch('homeassistant.components.melissa'):
            api = melissa_mock()
            device = (await api.async_fetch_devices())[_SERIAL]
            thermostat = MelissaClimate(api, _SERIAL, device)
            await thermostat.async_update()
            assert SPEED_LOW == thermostat.current_fan_mode
            assert STATE_HEAT == thermostat.current_operation
            api.async_status = mock_coro_func(exception=KeyError('boom'))
            await thermostat.async_update()
            mocked_warning.assert_called_once_with(
                'Unable to update entity %s', thermostat.entity_id)


async def test_melissa_state_to_hass(hass):
    """Test for translate melissa states to hass."""
    with patch('homeassistant.components.melissa'):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        assert STATE_OFF == thermostat.melissa_state_to_hass(0)
        assert STATE_ON == thermostat.melissa_state_to_hass(1)
        assert STATE_IDLE == thermostat.melissa_state_to_hass(2)
        assert thermostat.melissa_state_to_hass(3) is None


async def test_melissa_op_to_hass(hass):
    """Test for translate melissa operations to hass."""
    with patch('homeassistant.components.melissa'):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        assert STATE_FAN_ONLY == thermostat.melissa_op_to_hass(1)
        assert STATE_HEAT == thermostat.melissa_op_to_hass(2)
        assert STATE_COOL == thermostat.melissa_op_to_hass(3)
        assert STATE_DRY == thermostat.melissa_op_to_hass(4)
        assert thermostat.melissa_op_to_hass(5) is None


async def test_melissa_fan_to_hass(hass):
    """Test for translate melissa fan state to hass."""
    with patch('homeassistant.components.melissa'):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        assert STATE_AUTO == thermostat.melissa_fan_to_hass(0)
        assert SPEED_LOW == thermostat.melissa_fan_to_hass(1)
        assert SPEED_MEDIUM == thermostat.melissa_fan_to_hass(2)
        assert SPEED_HIGH == thermostat.melissa_fan_to_hass(3)
        assert thermostat.melissa_fan_to_hass(4) is None


async def test_hass_mode_to_melissa(hass):
    """Test for hass operations to melssa."""
    with patch('homeassistant.components.melissa.climate._LOGGER.warning'
               ) as mocked_warning:
        with patch('homeassistant.components.melissa'):
            api = melissa_mock()
            device = (await api.async_fetch_devices())[_SERIAL]
            thermostat = MelissaClimate(api, _SERIAL, device)
            assert 1 == thermostat.hass_mode_to_melissa(STATE_FAN_ONLY)
            assert 2 == thermostat.hass_mode_to_melissa(STATE_HEAT)
            assert 3 == thermostat.hass_mode_to_melissa(STATE_COOL)
            assert 4 == thermostat.hass_mode_to_melissa(STATE_DRY)
            thermostat.hass_mode_to_melissa("test")
            mocked_warning.assert_called_once_with(
                "Melissa have no setting for %s mode", "test")


async def test_hass_fan_to_melissa(hass):
    """Test for translate melissa states to hass."""
    with patch(
            'homeassistant.components.melissa.climate._LOGGER.warning'
            ) as mocked_warning:
        with patch('homeassistant.components.melissa'):
            api = melissa_mock()
            device = (await api.async_fetch_devices())[_SERIAL]
            thermostat = MelissaClimate(api, _SERIAL, device)
            assert 0 == thermostat.hass_fan_to_melissa(STATE_AUTO)
            assert 1 == thermostat.hass_fan_to_melissa(SPEED_LOW)
            assert 2 == thermostat.hass_fan_to_melissa(SPEED_MEDIUM)
            assert 3 == thermostat.hass_fan_to_melissa(SPEED_HIGH)
            thermostat.hass_fan_to_melissa("test")
            mocked_warning.assert_called_once_with(
                "Melissa have no setting for %s fan mode", "test")
