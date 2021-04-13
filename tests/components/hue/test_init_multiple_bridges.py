"""Test Hue init with multiple bridges."""
from unittest.mock import AsyncMock, Mock, patch

from aiohue.groups import Groups
from aiohue.lights import Lights
from aiohue.scenes import Scenes
from aiohue.sensors import Sensors
import pytest

from homeassistant import config_entries
from homeassistant.components import hue
from homeassistant.components.hue import sensor_base as hue_sensor_base
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def setup_component(hass):
    """Hue component."""
    with patch.object(hue, "async_setup_entry", return_value=True):
        assert (
            await async_setup_component(
                hass,
                hue.DOMAIN,
                {},
            )
            is True
        )


async def test_hue_activate_scene_both_responds(
    hass, mock_bridge1, mock_bridge2, mock_config_entry1, mock_config_entry2
):
    """Test that makes both bridges successfully activate a scene."""

    await setup_component(hass)

    await setup_bridge(hass, mock_bridge1, mock_config_entry1)
    await setup_bridge(hass, mock_bridge2, mock_config_entry2)

    with patch.object(
        mock_bridge1, "hue_activate_scene", return_value=None
    ) as mock_hue_activate_scene1, patch.object(
        mock_bridge2, "hue_activate_scene", return_value=None
    ) as mock_hue_activate_scene2:
        await hass.services.async_call(
            "hue",
            "hue_activate_scene",
            {"group_name": "group_2", "scene_name": "my_scene"},
            blocking=True,
        )

    mock_hue_activate_scene1.assert_called_once()
    mock_hue_activate_scene2.assert_called_once()


async def test_hue_activate_scene_one_responds(
    hass, mock_bridge1, mock_bridge2, mock_config_entry1, mock_config_entry2
):
    """Test that makes only one bridge successfully activate a scene."""

    await setup_component(hass)

    await setup_bridge(hass, mock_bridge1, mock_config_entry1)
    await setup_bridge(hass, mock_bridge2, mock_config_entry2)

    with patch.object(
        mock_bridge1, "hue_activate_scene", return_value=None
    ) as mock_hue_activate_scene1, patch.object(
        mock_bridge2, "hue_activate_scene", return_value=False
    ) as mock_hue_activate_scene2:
        await hass.services.async_call(
            "hue",
            "hue_activate_scene",
            {"group_name": "group_2", "scene_name": "my_scene"},
            blocking=True,
        )

    mock_hue_activate_scene1.assert_called_once()
    mock_hue_activate_scene2.assert_called_once()


async def test_hue_activate_scene_zero_responds(
    hass, mock_bridge1, mock_bridge2, mock_config_entry1, mock_config_entry2
):
    """Test that makes no bridge successfully activate a scene."""

    await setup_component(hass)

    await setup_bridge(hass, mock_bridge1, mock_config_entry1)
    await setup_bridge(hass, mock_bridge2, mock_config_entry2)

    with patch.object(
        mock_bridge1, "hue_activate_scene", return_value=False
    ) as mock_hue_activate_scene1, patch.object(
        mock_bridge2, "hue_activate_scene", return_value=False
    ) as mock_hue_activate_scene2:
        await hass.services.async_call(
            "hue",
            "hue_activate_scene",
            {"group_name": "group_2", "scene_name": "my_scene"},
            blocking=True,
        )

    # both were retried
    assert mock_hue_activate_scene1.call_count == 2
    assert mock_hue_activate_scene2.call_count == 2


async def setup_bridge(hass, mock_bridge, config_entry):
    """Load the Hue light platform with the provided bridge."""
    mock_bridge.config_entry = config_entry
    config_entry.add_to_hass(hass)
    with patch("homeassistant.components.hue.HueBridge", return_value=mock_bridge):
        await hass.config_entries.async_setup(config_entry.entry_id)


@pytest.fixture
def mock_config_entry1(hass):
    """Mock a config entry."""
    return create_config_entry()


@pytest.fixture
def mock_config_entry2(hass):
    """Mock a config entry."""
    return create_config_entry()


def create_config_entry():
    """Mock a config entry."""
    return MockConfigEntry(
        domain=hue.DOMAIN,
        data={"host": "mock-host"},
        connection_class=config_entries.CONN_CLASS_LOCAL_POLL,
    )


@pytest.fixture
def mock_bridge1(hass):
    """Mock a Hue bridge."""
    return create_mock_bridge(hass)


@pytest.fixture
def mock_bridge2(hass):
    """Mock a Hue bridge."""
    return create_mock_bridge(hass)


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
        async_setup=AsyncMock(return_value=True),
    )
    bridge.sensor_manager = hue_sensor_base.SensorManager(bridge)
    bridge.mock_requests = []

    async def mock_request(method, path, **kwargs):
        kwargs["method"] = method
        kwargs["path"] = path
        bridge.mock_requests.append(kwargs)
        return {}

    async def async_request_call(task):
        await task()

    bridge.async_request_call = async_request_call
    bridge.api.config.apiversion = "9.9.9"
    bridge.api.lights = Lights({}, mock_request)
    bridge.api.groups = Groups({}, mock_request)
    bridge.api.sensors = Sensors({}, mock_request)
    bridge.api.scenes = Scenes({}, mock_request)
    return bridge
