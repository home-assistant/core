"""Test for Melissa climate component."""
import json
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.components.climate.const import (
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.melissa import DATA_MELISSA, climate as melissa
from homeassistant.components.melissa.climate import MelissaClimate
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

from tests.common import load_fixture

_SERIAL = "12345678"


def melissa_mock():
    """Use this to mock the melissa api."""
    api = Mock()
    api.async_fetch_devices = AsyncMock(
        return_value=json.loads(load_fixture("fetch_devices.json", "melissa"))
    )
    api.async_status = AsyncMock(
        return_value=json.loads(load_fixture("status.json", "melissa"))
    )
    api.async_cur_settings = AsyncMock(
        return_value=json.loads(load_fixture("cur_settings.json", "melissa"))
    )

    api.async_send = AsyncMock(return_value=True)

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

    api.STATE = "state"
    api.MODE = "mode"
    api.FAN = "fan"
    api.TEMP = "temp"
    return api


async def test_setup_platform(hass):
    """Test setup_platform."""
    with patch(
        "homeassistant.components.melissa.climate.MelissaClimate"
    ) as mocked_thermostat:
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = mocked_thermostat(api, device["serial_number"], device)
        thermostats = [thermostat]

        hass.data[DATA_MELISSA] = api

        config = {}
        add_entities = Mock()
        discovery_info = {}

        await melissa.async_setup_platform(hass, config, add_entities, discovery_info)
        add_entities.assert_called_once_with(thermostats)


async def test_get_name(hass):
    """Test name property."""
    with patch("homeassistant.components.melissa"):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        assert thermostat.name == "Melissa 12345678"


async def test_current_fan_mode(hass):
    """Test current_fan_mode property."""
    with patch("homeassistant.components.melissa"):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        await thermostat.async_update()
        assert thermostat.fan_mode == FAN_LOW

        thermostat._cur_settings = None
        assert thermostat.fan_mode is None


async def test_current_temperature(hass):
    """Test current temperature."""
    with patch("homeassistant.components.melissa"):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        assert thermostat.current_temperature == 27.4


async def test_current_temperature_no_data(hass):
    """Test current temperature without data."""
    with patch("homeassistant.components.melissa"):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        thermostat._data = None
        assert thermostat.current_temperature is None


async def test_target_temperature_step(hass):
    """Test current target_temperature_step."""
    with patch("homeassistant.components.melissa"):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        assert thermostat.target_temperature_step == 1


async def test_current_operation(hass):
    """Test current operation."""
    with patch("homeassistant.components.melissa"):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        await thermostat.async_update()
        assert thermostat.state == HVACMode.HEAT

        thermostat._cur_settings = None
        assert thermostat.hvac_action is None


async def test_operation_list(hass):
    """Test the operation list."""
    with patch("homeassistant.components.melissa"):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        assert [
            HVACMode.HEAT,
            HVACMode.COOL,
            HVACMode.DRY,
            HVACMode.FAN_ONLY,
            HVACMode.OFF,
        ] == thermostat.hvac_modes


async def test_fan_modes(hass):
    """Test the fan list."""
    with patch("homeassistant.components.melissa"):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        assert ["auto", FAN_HIGH, FAN_MEDIUM, FAN_LOW] == thermostat.fan_modes


async def test_target_temperature(hass):
    """Test target temperature."""
    with patch("homeassistant.components.melissa"):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        await thermostat.async_update()
        assert thermostat.target_temperature == 16

        thermostat._cur_settings = None
        assert thermostat.target_temperature is None


async def test_state(hass):
    """Test state."""
    with patch("homeassistant.components.melissa"):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        await thermostat.async_update()
        assert thermostat.state == HVACMode.HEAT

        thermostat._cur_settings = None
        assert thermostat.state is None


async def test_temperature_unit(hass):
    """Test temperature unit."""
    with patch("homeassistant.components.melissa"):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        assert thermostat.temperature_unit == TEMP_CELSIUS


async def test_min_temp(hass):
    """Test min temp."""
    with patch("homeassistant.components.melissa"):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        assert thermostat.min_temp == 16


async def test_max_temp(hass):
    """Test max temp."""
    with patch("homeassistant.components.melissa"):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        assert thermostat.max_temp == 30


async def test_supported_features(hass):
    """Test supported_features property."""
    with patch("homeassistant.components.melissa"):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        features = (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
        )
        assert thermostat.supported_features == features


async def test_set_temperature(hass):
    """Test set_temperature."""
    with patch("homeassistant.components.melissa"):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        await thermostat.async_update()
        await thermostat.async_set_temperature(**{ATTR_TEMPERATURE: 25})
        assert thermostat.target_temperature == 25


async def test_fan_mode(hass):
    """Test set_fan_mode."""
    with patch("homeassistant.components.melissa"):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        await thermostat.async_update()
        await hass.async_block_till_done()
        await thermostat.async_set_fan_mode(FAN_HIGH)
        await hass.async_block_till_done()
        assert thermostat.fan_mode == FAN_HIGH


async def test_set_operation_mode(hass):
    """Test set_operation_mode."""
    with patch("homeassistant.components.melissa"):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        await thermostat.async_update()
        await hass.async_block_till_done()
        await thermostat.async_set_hvac_mode(HVACMode.COOL)
        await hass.async_block_till_done()
        assert thermostat.hvac_mode == HVACMode.COOL


async def test_send(hass):
    """Test send."""
    with patch("homeassistant.components.melissa"):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        await thermostat.async_update()
        await hass.async_block_till_done()
        await thermostat.async_send({"fan": api.FAN_MEDIUM})
        await hass.async_block_till_done()
        assert thermostat.fan_mode == FAN_MEDIUM
        api.async_send.return_value = AsyncMock(return_value=False)
        thermostat._cur_settings = None
        await thermostat.async_send({"fan": api.FAN_LOW})
        await hass.async_block_till_done()
        assert FAN_LOW != thermostat.fan_mode
        assert thermostat._cur_settings is None


async def test_update(hass):
    """Test update."""
    with patch(
        "homeassistant.components.melissa.climate._LOGGER.warning"
    ) as mocked_warning, patch("homeassistant.components.melissa"):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        await thermostat.async_update()
        assert thermostat.fan_mode == FAN_LOW
        assert thermostat.state == HVACMode.HEAT
        api.async_status = AsyncMock(side_effect=KeyError("boom"))
        await thermostat.async_update()
        mocked_warning.assert_called_once_with(
            "Unable to update entity %s", thermostat.entity_id
        )


async def test_melissa_op_to_hass(hass):
    """Test for translate melissa operations to hass."""
    with patch("homeassistant.components.melissa"):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        assert thermostat.melissa_op_to_hass(1) == HVACMode.FAN_ONLY
        assert thermostat.melissa_op_to_hass(2) == HVACMode.HEAT
        assert thermostat.melissa_op_to_hass(3) == HVACMode.COOL
        assert thermostat.melissa_op_to_hass(4) == HVACMode.DRY
        assert thermostat.melissa_op_to_hass(5) is None


async def test_melissa_fan_to_hass(hass):
    """Test for translate melissa fan state to hass."""
    with patch("homeassistant.components.melissa"):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        assert thermostat.melissa_fan_to_hass(0) == "auto"
        assert thermostat.melissa_fan_to_hass(1) == FAN_LOW
        assert thermostat.melissa_fan_to_hass(2) == FAN_MEDIUM
        assert thermostat.melissa_fan_to_hass(3) == FAN_HIGH
        assert thermostat.melissa_fan_to_hass(4) is None


async def test_hass_mode_to_melissa(hass):
    """Test for hass operations to melssa."""
    with patch(
        "homeassistant.components.melissa.climate._LOGGER.warning"
    ) as mocked_warning, patch("homeassistant.components.melissa"):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        assert thermostat.hass_mode_to_melissa(HVACMode.FAN_ONLY) == 1
        assert thermostat.hass_mode_to_melissa(HVACMode.HEAT) == 2
        assert thermostat.hass_mode_to_melissa(HVACMode.COOL) == 3
        assert thermostat.hass_mode_to_melissa(HVACMode.DRY) == 4
        thermostat.hass_mode_to_melissa("test")
        mocked_warning.assert_called_once_with(
            "Melissa have no setting for %s mode", "test"
        )


async def test_hass_fan_to_melissa(hass):
    """Test for translate melissa states to hass."""
    with patch(
        "homeassistant.components.melissa.climate._LOGGER.warning"
    ) as mocked_warning, patch("homeassistant.components.melissa"):
        api = melissa_mock()
        device = (await api.async_fetch_devices())[_SERIAL]
        thermostat = MelissaClimate(api, _SERIAL, device)
        assert thermostat.hass_fan_to_melissa("auto") == 0
        assert thermostat.hass_fan_to_melissa(FAN_LOW) == 1
        assert thermostat.hass_fan_to_melissa(FAN_MEDIUM) == 2
        assert thermostat.hass_fan_to_melissa(FAN_HIGH) == 3
        thermostat.hass_fan_to_melissa("test")
        mocked_warning.assert_called_once_with(
            "Melissa have no setting for %s fan mode", "test"
        )
