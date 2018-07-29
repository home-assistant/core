"""Setup some common test helper things."""
import asyncio
import functools
import logging
import os
from unittest.mock import patch, MagicMock

import pytest
import requests_mock as _requests_mock

from homeassistant import util
from homeassistant.util import location

from tests.common import (
    async_test_home_assistant, INSTANCES, async_mock_mqtt_component, mock_coro,
    mock_storage as mock_storage)
from tests.test_util.aiohttp import mock_aiohttp_client
from tests.mock.zwave import MockNetwork, MockOption

if os.environ.get('UVLOOP') == '1':
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

logging.basicConfig(level=logging.DEBUG)
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)


def check_real(func):
    """Force a function to require a keyword _test_real to be passed in."""
    @functools.wraps(func)
    def guard_func(*args, **kwargs):
        real = kwargs.pop('_test_real', None)

        if not real:
            raise Exception('Forgot to mock or pass "_test_real=True" to %s',
                            func.__name__)

        return func(*args, **kwargs)

    return guard_func


# Guard a few functions that would make network connections
location.detect_location_info = check_real(location.detect_location_info)
location.elevation = check_real(location.elevation)
util.get_local_ip = lambda: '127.0.0.1'


@pytest.fixture(autouse=True)
def verify_cleanup():
    """Verify that the test has cleaned up resources correctly."""
    yield

    if len(INSTANCES) >= 2:
        count = len(INSTANCES)
        for inst in INSTANCES:
            inst.stop()
        pytest.exit("Detected non stopped instances "
                    "({}), aborting test run".format(count))


@pytest.fixture
def hass_storage():
    """Fixture to mock storage."""
    with mock_storage() as stored_data:
        yield stored_data


@pytest.fixture
def hass(loop, hass_storage):
    """Fixture to provide a test instance of HASS."""
    hass = loop.run_until_complete(async_test_home_assistant(loop))

    yield hass

    loop.run_until_complete(hass.async_stop())


@pytest.fixture
def requests_mock():
    """Fixture to provide a requests mocker."""
    with _requests_mock.mock() as m:
        yield m


@pytest.fixture
def aioclient_mock():
    """Fixture to mock aioclient calls."""
    with mock_aiohttp_client() as mock_session:
        yield mock_session


@pytest.fixture
def mqtt_mock(loop, hass):
    """Fixture to mock MQTT."""
    client = loop.run_until_complete(async_mock_mqtt_component(hass))
    client.reset_mock()
    return client


@pytest.fixture
def mock_openzwave():
    """Mock out Open Z-Wave."""
    base_mock = MagicMock()
    libopenzwave = base_mock.libopenzwave
    libopenzwave.__file__ = 'test'
    base_mock.network.ZWaveNetwork = MockNetwork
    base_mock.option.ZWaveOption = MockOption

    with patch.dict('sys.modules', {
        'libopenzwave': libopenzwave,
        'openzwave.option': base_mock.option,
        'openzwave.network': base_mock.network,
        'openzwave.group': base_mock.group,
    }):
        yield base_mock


@pytest.fixture
def mock_device_tracker_conf():
    """Prevent device tracker from reading/writing data."""
    devices = []

    async def mock_update_config(path, id, entity):
        devices.append(entity)

    with patch(
        'homeassistant.components.device_tracker'
        '.DeviceTracker.async_update_config',
            side_effect=mock_update_config
    ), patch(
        'homeassistant.components.device_tracker.async_load_config',
            side_effect=lambda *args: mock_coro(devices)
    ):
        yield devices
