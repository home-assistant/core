"""Test helpers for Hue."""
from collections import deque
from unittest.mock import Mock, patch

from aiohue.groups import Groups
from aiohue.lights import Lights
from aiohue.sensors import Sensors
import pytest

from homeassistant import config_entries
from homeassistant.components import hue
from homeassistant.components.hue import sensor_base as hue_sensor_base


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
        api=Mock(),
        reset_jobs=[],
        spec=hue.HueBridge,
    )
    bridge.sensor_manager = hue_sensor_base.SensorManager(bridge)
    bridge.mock_requests = []
    # We're using a deque so we can schedule multiple responses
    # and also means that `popleft()` will blow up if we get more updates
    # than expected.
    bridge.mock_light_responses = deque()
    bridge.mock_group_responses = deque()
    bridge.mock_sensor_responses = deque()

    async def mock_request(method, path, **kwargs):
        kwargs["method"] = method
        kwargs["path"] = path
        bridge.mock_requests.append(kwargs)

        if path == "lights":
            return bridge.mock_light_responses.popleft()
        if path == "groups":
            return bridge.mock_group_responses.popleft()
        if path == "sensors":
            return bridge.mock_sensor_responses.popleft()
        return None

    async def async_request_call(task):
        await task()

    bridge.async_request_call = async_request_call
    bridge.api.config.apiversion = "9.9.9"
    bridge.api.lights = Lights({}, mock_request)
    bridge.api.groups = Groups({}, mock_request)
    bridge.api.sensors = Sensors({}, mock_request)
    return bridge


@pytest.fixture
def mock_bridge(hass):
    """Mock a Hue bridge."""
    return create_mock_bridge(hass)


async def setup_bridge_for_sensors(hass, mock_bridge, hostname=None):
    """Load the Hue platform with the provided bridge for sensor-related platforms."""
    if hostname is None:
        hostname = "mock-host"
    hass.config.components.add(hue.DOMAIN)
    config_entry = config_entries.ConfigEntry(
        1,
        hue.DOMAIN,
        "Mock Title",
        {"host": hostname},
        "test",
        config_entries.CONN_CLASS_LOCAL_POLL,
        system_options={},
    )
    mock_bridge.config_entry = config_entry
    hass.data[hue.DOMAIN] = {config_entry.entry_id: mock_bridge}
    await hass.config_entries.async_forward_entry_setup(config_entry, "binary_sensor")
    await hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
    # simulate a full setup by manually adding the bridge config entry
    hass.config_entries._entries.append(config_entry)

    # and make sure it completes before going further
    await hass.async_block_till_done()
