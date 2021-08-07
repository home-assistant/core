"""Test helpers for Hue."""
from collections import deque
import logging
from unittest.mock import AsyncMock, Mock, patch

from aiohue.groups import Groups
from aiohue.lights import Lights
from aiohue.scenes import Scenes
from aiohue.sensors import Sensors
import pytest

from homeassistant.components import hue
from homeassistant.components.hue import sensor_base as hue_sensor_base

from tests.common import MockConfigEntry
from tests.components.light.conftest import mock_light_profiles  # noqa: F401


@pytest.fixture(autouse=True)
def no_request_delay():
    """Make the request refresh delay 0 for instant tests."""
    with patch("homeassistant.components.hue.light.REQUEST_REFRESH_DELAY", 0):
        yield


def create_mock_bridge(hass):
    """Create a mock Hue bridge."""
    bridge = Mock(
        hass=hass,
        available=True,
        authorized=True,
        allow_unreachable=False,
        allow_groups=False,
        api=create_mock_api(hass),
        config_entry=None,
        reset_jobs=[],
        spec=hue.HueBridge,
    )
    bridge.sensor_manager = hue_sensor_base.SensorManager(bridge)
    bridge.mock_requests = bridge.api.mock_requests
    bridge.mock_light_responses = bridge.api.mock_light_responses
    bridge.mock_group_responses = bridge.api.mock_group_responses
    bridge.mock_sensor_responses = bridge.api.mock_sensor_responses

    async def async_setup():
        if bridge.config_entry:
            hass.data.setdefault(hue.DOMAIN, {})[bridge.config_entry.entry_id] = bridge
        return True

    bridge.async_setup = async_setup

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
def mock_api(hass):
    """Mock the Hue api."""
    return create_mock_api(hass)


def create_mock_api(hass):
    """Create a mock API."""
    api = Mock(initialize=AsyncMock())
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

    api.lights = Lights(logger, {}, [], mock_request)
    api.groups = Groups(logger, {}, [], mock_request)
    api.sensors = Sensors(logger, {}, [], mock_request)
    api.scenes = Scenes(logger, {}, [], mock_request)
    return api


@pytest.fixture
def mock_bridge(hass):
    """Mock a Hue bridge."""
    return create_mock_bridge(hass)


async def setup_bridge_for_sensors(hass, mock_bridge, hostname=None):
    """Load the Hue platform with the provided bridge for sensor-related platforms."""
    if hostname is None:
        hostname = "mock-host"
    hass.config.components.add(hue.DOMAIN)
    config_entry = MockConfigEntry(
        domain=hue.DOMAIN,
        title="Mock Title",
        data={"host": hostname},
    )
    mock_bridge.config_entry = config_entry
    hass.data[hue.DOMAIN] = {config_entry.entry_id: mock_bridge}
    await hass.config_entries.async_forward_entry_setup(config_entry, "binary_sensor")
    await hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
    # simulate a full setup by manually adding the bridge config entry
    config_entry.add_to_hass(hass)

    # and make sure it completes before going further
    await hass.async_block_till_done()
