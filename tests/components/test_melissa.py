"""The test for the Melissa Climate component."""
import json
from unittest.mock import Mock

import pytest

from tests.common import MockDependency, mock_coro_func, load_fixture

from homeassistant.components import melissa

VALID_CONFIG = {
    "melissa": {
        "username": "********",
        "password": "********",
    }
}


@pytest.fixture
def melissa_mock():
    """Use this to mock the melissa api."""
    api = MockDependency('melissa.AsyncMelissa')
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


async def test_setup(hass):
    """Test setting up the Melissa component."""
    with MockDependency('melissa') as mocked_melissa:
        mocked_melissa.AsyncMelissa().async_connect = mock_coro_func()
        await melissa.async_setup(hass, VALID_CONFIG)

        mocked_melissa.AsyncMelissa.assert_called_with(
            username="********", password="********")

        assert melissa.DATA_MELISSA in hass.data
        assert isinstance(hass.data[melissa.DATA_MELISSA], type(
                mocked_melissa.AsyncMelissa()))
