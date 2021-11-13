"""Test helpers for Hue."""
from collections import deque
import logging
from unittest.mock import AsyncMock, Mock, patch

import aiohue
from aiohue.v1.groups import Groups
from aiohue.v1.lights import Lights
from aiohue.v1.scenes import Scenes
from aiohue.v1.sensors import Sensors
import pytest

from homeassistant.components import hue
from homeassistant.components.hue.v1 import sensor_base as hue_sensor_base

from tests.common import MockConfigEntry
from tests.components.light.conftest import mock_light_profiles  # noqa: F401


@pytest.fixture(autouse=True)
def no_request_delay():
    """Make the request refresh delay 0 for instant tests."""
    with patch("homeassistant.components.hue.const.REQUEST_REFRESH_DELAY", 0):
        yield


def create_mock_bridge(hass, api_version=1):
    """Create a mocked HueBridge instance."""
    bridge = Mock(
        hass=hass,
        authorized=True,
        config_entry=None,
        reset_jobs=[],
        api_version=api_version,
        spec=hue.HueBridge,
    )

    if bridge.api_version == 2:
        bridge.api = create_mock_api_v2(hass)
    else:
        bridge.api = create_mock_api_v1(hass)
        bridge.sensor_manager = hue_sensor_base.SensorManager(bridge)
        bridge.mock_requests = bridge.api.mock_requests
        bridge.mock_light_responses = bridge.api.mock_light_responses
        bridge.mock_group_responses = bridge.api.mock_group_responses
        bridge.mock_sensor_responses = bridge.api.mock_sensor_responses

    async def async_initialize_bridge():
        if bridge.config_entry:
            hass.data.setdefault(hue.DOMAIN, {})[bridge.config_entry.entry_id] = bridge
        return True

    bridge.async_initialize_bridge = async_initialize_bridge

    async def async_request_call(task):
        await task()

    bridge.async_request_call = async_request_call

    async def async_reset():
        if bridge.config_entry:
            hass.data[hue.DOMAIN].pop(bridge.config_entry.entry_id)
        return True

    bridge.async_reset = async_reset

    return bridge


@pytest.fixture
def mock_api_v1(hass):
    """Mock the Hue V1 api."""
    return create_mock_api_v1(hass)


@pytest.fixture
def mock_api_v2(hass):
    """Mock the Hue V2 api."""
    return create_mock_api_v2(hass)


def create_mock_api_v1(hass):
    """Create a mock V1 API."""
    api = Mock(spec=aiohue.HueBridgeV1)
    api.initialize = AsyncMock()
    api.mock_requests = []
    api.mock_light_responses = deque()
    api.mock_group_responses = deque()
    api.mock_sensor_responses = deque()
    api.mock_scene_responses = deque()

    async def mock_request(method, path, **kwargs):
        kwargs["method"] = method
        kwargs["path"] = path
        api.mock_requests.append(kwargs)

        if path == "lights":
            return api.mock_light_responses.popleft()
        if path == "groups":
            return api.mock_group_responses.popleft()
        if path == "sensors":
            return api.mock_sensor_responses.popleft()
        if path == "scenes":
            return api.mock_scene_responses.popleft()
        return None

    logger = logging.getLogger(__name__)

    api.config = Mock(
        bridgeid="ff:ff:ff:ff:ff:ff",
        mac="aa:bb:cc:dd:ee:ff",
        modelid="BSB002",
        apiversion="9.9.9",
        swversion="1935144040",
    )
    api.config.name = "Home"

    api.lights = Lights(logger, {}, mock_request)
    api.groups = Groups(logger, {}, mock_request)
    api.sensors = Sensors(logger, {}, mock_request)
    api.scenes = Scenes(logger, {}, mock_request)
    return api


def create_mock_api_v2(hass):
    """Create a mock V2 API."""
    api = Mock(spec=aiohue.HueBridgeV1)
    api.initialize = AsyncMock()
    return api


@pytest.fixture
def mock_bridge_v1(hass):
    """Mock a Hue bridge with V1 api."""
    return create_mock_bridge(hass, api_version=1)


@pytest.fixture
def mock_bridge_v2(hass):
    """Mock a Hue bridge with V2 api."""
    return create_mock_bridge(hass, api_version=2)


async def setup_bridge_for_sensors(hass, mock_bridge_v1, hostname=None):
    """Load the Hue platform with the provided bridge for sensor-related platforms."""
    if hostname is None:
        hostname = "mock-host"
    hass.config.components.add(hue.DOMAIN)
    config_entry = MockConfigEntry(
        domain=hue.DOMAIN,
        title="Mock Title",
        data={"host": hostname, "api_version": 1},
    )
    mock_bridge_v1.config_entry = config_entry
    hass.data[hue.DOMAIN] = {config_entry.entry_id: mock_bridge_v1}
    await hass.config_entries.async_forward_entry_setup(config_entry, "binary_sensor")
    await hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
    # simulate a full setup by manually adding the bridge config entry
    config_entry.add_to_hass(hass)

    # and make sure it completes before going further
    await hass.async_block_till_done()
