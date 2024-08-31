"""Test helpers for Hue."""
import asyncio
from collections import deque
import json
import logging
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import aiohue.v1 as aiohue_v1
import aiohue.v2 as aiohue_v2
from aiohue.v2.controllers.events import EventType
import pytest

from homeassistant.components import hue
from homeassistant.components.hue.v1 import sensor_base as hue_sensor_base
from homeassistant.components.hue.v2.device import async_setup_devices
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    async_mock_service,
    load_fixture,
    mock_device_registry,
)
from tests.components.hue.const import FAKE_BRIDGE, FAKE_BRIDGE_DEVICE


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

    bridge.logger = logging.getLogger(__name__)

    if bridge.api_version == 2:
        bridge.api = create_mock_api_v2(hass)
        bridge.mock_requests = bridge.api.mock_requests
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
        if bridge.api_version == 2:
            await async_setup_devices(bridge)
        return True

    bridge.async_initialize_bridge = async_initialize_bridge

    async def async_request_call(task, *args, **kwargs):
        await task(*args, **kwargs)

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
    api = Mock(spec=aiohue_v1.HueBridgeV1)
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
        bridge_id="ff:ff:ff:ff:ff:ff",
        mac_address="aa:bb:cc:dd:ee:ff",
        model_id="BSB002",
        apiversion="9.9.9",
        software_version="1935144040",
    )
    api.config.name = "Home"

    api.lights = aiohue_v1.Lights(logger, {}, mock_request)
    api.groups = aiohue_v1.Groups(logger, {}, mock_request)
    api.sensors = aiohue_v1.Sensors(logger, {}, mock_request)
    api.scenes = aiohue_v1.Scenes(logger, {}, mock_request)
    return api


@pytest.fixture(scope="session")
def v2_resources_test_data():
    """Load V2 resources mock data."""
    return json.loads(load_fixture("hue/v2_resources.json"))


def create_mock_api_v2(hass):
    """Create a mock V2 API."""
    api = Mock(spec=aiohue_v2.HueBridgeV2)
    api.initialize = AsyncMock()
    api.mock_requests = []

    api.logger = logging.getLogger(__name__)
    api.config = aiohue_v2.ConfigController(api)
    api.events = aiohue_v2.EventStream(api)
    api.devices = aiohue_v2.DevicesController(api)
    api.lights = aiohue_v2.LightsController(api)
    api.sensors = aiohue_v2.SensorsController(api)
    api.groups = aiohue_v2.GroupsController(api)
    api.scenes = aiohue_v2.ScenesController(api)

    async def mock_request(method, path, **kwargs):
        kwargs["method"] = method
        kwargs["path"] = path
        api.mock_requests.append(kwargs)
        return kwargs.get("json")

    api.request = mock_request

    async def load_test_data(data: list[dict[str, Any]]):
        """Load test data into controllers."""

        # append default bridge if none explicitly given in test data
        if not any(x for x in data if x["type"] == "bridge"):
            data.append(FAKE_BRIDGE)
            data.append(FAKE_BRIDGE_DEVICE)

        await asyncio.gather(
            api.config.initialize(data),
            api.devices.initialize(data),
            api.lights.initialize(data),
            api.scenes.initialize(data),
            api.sensors.initialize(data),
            api.groups.initialize(data),
        )

    def emit_event(event_type, data):
        """Emit an event from a (hue resource) dict."""
        api.events.emit(EventType(event_type), data)

    api.load_test_data = load_test_data
    api.emit_event = emit_event
    # mock context manager too
    api.__aenter__ = AsyncMock(return_value=api)
    api.__aexit__ = AsyncMock()
    return api


@pytest.fixture
def mock_bridge_v1(hass):
    """Mock a Hue bridge with V1 api."""
    return create_mock_bridge(hass, api_version=1)


@pytest.fixture
def mock_bridge_v2(hass):
    """Mock a Hue bridge with V2 api."""
    return create_mock_bridge(hass, api_version=2)


@pytest.fixture
def mock_config_entry_v1(hass):
    """Mock a config entry for a Hue V1 bridge."""
    return create_config_entry(api_version=1)


@pytest.fixture
def mock_config_entry_v2(hass):
    """Mock a config entry."""
    return create_config_entry(api_version=2)


def create_config_entry(api_version=1, host="mock-host"):
    """Mock a config entry for a Hue bridge."""
    return MockConfigEntry(
        domain=hue.DOMAIN,
        title=f"Mock bridge {api_version}",
        data={"host": host, "api_version": api_version, "api_key": ""},
    )


async def setup_component(hass):
    """Mock setup Hue component."""
    with patch.object(hue, "async_setup_entry", return_value=True):
        assert (
            await async_setup_component(
                hass,
                hue.DOMAIN,
                {},
            )
            is True
        )


async def setup_bridge(hass, mock_bridge, config_entry):
    """Load the Hue integration with the provided bridge."""
    mock_bridge.config_entry = config_entry
    with patch.object(
        hue.migration, "is_v2_bridge", return_value=mock_bridge.api_version == 2
    ):
        config_entry.add_to_hass(hass)
        with patch("homeassistant.components.hue.HueBridge", return_value=mock_bridge):
            await hass.config_entries.async_setup(config_entry.entry_id)


async def setup_platform(
    hass,
    mock_bridge,
    platforms,
    hostname=None,
):
    """Load the Hue integration with the provided bridge for given platform(s)."""
    if not isinstance(platforms, (list, tuple)):
        platforms = [platforms]
    if hostname is None:
        hostname = "mock-host"
    hass.config.components.add(hue.DOMAIN)
    config_entry = create_config_entry(
        api_version=mock_bridge.api_version, host=hostname
    )
    mock_bridge.config_entry = config_entry
    hass.data[hue.DOMAIN] = {config_entry.entry_id: mock_bridge}

    # simulate a full setup by manually adding the bridge config entry
    await setup_bridge(hass, mock_bridge, config_entry)
    assert await async_setup_component(hass, hue.DOMAIN, {}) is True
    await hass.async_block_till_done()

    for platform in platforms:
        await hass.config_entries.async_forward_entry_setup(config_entry, platform)

    # and make sure it completes before going further
    await hass.async_block_till_done()


@pytest.fixture(name="device_reg")
def get_device_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture(name="calls")
def track_calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")
