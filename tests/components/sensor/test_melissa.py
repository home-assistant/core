"""Test for Melissa climate component."""
import json
from unittest.mock import Mock, patch

from homeassistant.components.sensor.melissa import MelissaTemperatureSensor, \
    MelissaHumiditySensor

from tests.common import load_fixture, mock_coro_func

from homeassistant.components.melissa import DATA_MELISSA
from homeassistant.components.sensor import melissa
from homeassistant.const import TEMP_CELSIUS


_SERIAL = "12345678"


def melissa_mock():
    """Use this to mock the melissa api."""
    api = Mock()
    api.async_fetch_devices = mock_coro_func(
        return_value=json.loads(load_fixture('melissa_fetch_devices.json')))
    api.async_status = mock_coro_func(return_value=json.loads(load_fixture(
        'melissa_status.json'
    )))

    api.TEMP = 'temp'
    api.HUMIDITY = 'humidity'
    return api


async def test_setup_platform(hass):
    """Test setup_platform."""
    with patch('homeassistant.components.melissa'):
        hass.data[DATA_MELISSA] = melissa_mock()

        config = {}
        async_add_entities = mock_coro_func()
        discovery_info = {}

        await melissa.async_setup_platform(
            hass, config, async_add_entities, discovery_info)


async def test_name(hass):
    """Test name property."""
    with patch('homeassistant.components.melissa'):
        mocked_melissa = melissa_mock()
        device = (await mocked_melissa.async_fetch_devices())[_SERIAL]
        temp = MelissaTemperatureSensor(device, mocked_melissa)
        hum = MelissaHumiditySensor(device, mocked_melissa)

        assert temp.name == '{0} {1}'.format(
            device['name'],
            temp._type
        )
        assert hum.name == '{0} {1}'.format(
            device['name'],
            hum._type
        )


async def test_state(hass):
    """Test state property."""
    with patch('homeassistant.components.melissa'):
        mocked_melissa = melissa_mock()
        device = (await mocked_melissa.async_fetch_devices())[_SERIAL]
        status = (await mocked_melissa.async_status())[_SERIAL]
        temp = MelissaTemperatureSensor(device, mocked_melissa)
        hum = MelissaHumiditySensor(device, mocked_melissa)
        await temp.async_update()
        assert temp.state == status[mocked_melissa.TEMP]
        await hum.async_update()
        assert hum.state == status[mocked_melissa.HUMIDITY]


async def test_unit_of_measurement(hass):
    """Test unit of measurement property."""
    with patch('homeassistant.components.melissa'):
        mocked_melissa = melissa_mock()
        device = (await mocked_melissa.async_fetch_devices())[_SERIAL]
        temp = MelissaTemperatureSensor(device, mocked_melissa)
        hum = MelissaHumiditySensor(device, mocked_melissa)
        assert temp.unit_of_measurement == TEMP_CELSIUS
        assert hum.unit_of_measurement == '%'


async def test_update(hass):
    """Test for update."""
    with patch('homeassistant.components.melissa'):
        mocked_melissa = melissa_mock()
        device = (await mocked_melissa.async_fetch_devices())[_SERIAL]
        temp = MelissaTemperatureSensor(device, mocked_melissa)
        hum = MelissaHumiditySensor(device, mocked_melissa)
        await temp.async_update()
        assert temp.state == 27.4
        await hum.async_update()
        assert hum.state == 18.7


async def test_update_keyerror(hass):
    """Test for faulty update."""
    with patch('homeassistant.components.melissa'):
        mocked_melissa = melissa_mock()
        device = (await mocked_melissa.async_fetch_devices())[_SERIAL]
        temp = MelissaTemperatureSensor(device, mocked_melissa)
        hum = MelissaHumiditySensor(device, mocked_melissa)
        mocked_melissa.async_status = mock_coro_func(return_value={})
        await temp.async_update()
        assert temp.state is None
        await hum.async_update()
        assert hum.state is None
