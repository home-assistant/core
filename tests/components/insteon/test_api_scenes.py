"""Test the Insteon Scenes APIs."""
import json
import os
from unittest.mock import AsyncMock, patch

from pyinsteon.constants import ResponseStatus
import pyinsteon.managers.scene_manager
import pytest

from homeassistant.components.insteon.api import async_load_api, scenes
from homeassistant.components.insteon.const import ID, TYPE
from homeassistant.core import HomeAssistant

from .mock_devices import MockDevices

from tests.common import load_fixture
from tests.typing import WebSocketGenerator


@pytest.fixture(name="scene_data", scope="session")
def aldb_data_fixture():
    """Load the controller state fixture data."""
    return json.loads(load_fixture("insteon/scene_data.json"))


@pytest.fixture(name="remove_json")
def remove_insteon_devices_json(hass):
    """Fixture to remove insteon_devices.json at the end of the test."""
    yield
    file = os.path.join(hass.config.config_dir, "insteon_devices.json")
    if os.path.exists(file):
        os.remove(file)


def _scene_to_array(scene):
    """Convert a scene object to a dictionary."""
    scene_list = []
    for device, links in scene["devices"].items():
        for link in links:
            link_dict = {}
            link_dict["address"] = device.id
            link_dict["data1"] = link.data1
            link_dict["data2"] = link.data2
            link_dict["data3"] = link.data3
            scene_list.append(link_dict)
    return scene_list


async def _setup(hass, hass_ws_client, scene_data):
    """Set up tests."""
    ws_client = await hass_ws_client(hass)
    devices = MockDevices()
    await devices.async_load()
    async_load_api(hass)
    for device in scene_data:
        addr = device["address"]
        aldb = device["aldb"]
        devices.fill_aldb(addr, aldb)
    return ws_client, devices


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_get_scenes(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, scene_data
) -> None:
    """Test getting all Insteon scenes."""
    ws_client, devices = await _setup(hass, hass_ws_client, scene_data)

    with patch.object(pyinsteon.managers.scene_manager, "devices", devices):
        await ws_client.send_json({ID: 1, TYPE: "insteon/scenes/get"})
        msg = await ws_client.receive_json()
        result = msg["result"]
        assert len(result) == 1
        assert len(result["20"]) == 3


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_get_scene(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, scene_data
) -> None:
    """Test getting an Insteon scene."""
    ws_client, devices = await _setup(hass, hass_ws_client, scene_data)

    with patch.object(pyinsteon.managers.scene_manager, "devices", devices):
        await ws_client.send_json({ID: 1, TYPE: "insteon/scene/get", "scene_id": 20})
        msg = await ws_client.receive_json()
        result = msg["result"]
        assert len(result["devices"]) == 3


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_save_scene(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, scene_data, remove_json
) -> None:
    """Test saving an Insteon scene."""
    ws_client, devices = await _setup(hass, hass_ws_client, scene_data)

    mock_add_or_update_scene = AsyncMock(return_value=(20, ResponseStatus.SUCCESS))

    with patch.object(
        pyinsteon.managers.scene_manager, "devices", devices
    ), patch.object(scenes, "async_add_or_update_scene", mock_add_or_update_scene):
        scene = await pyinsteon.managers.scene_manager.async_get_scene(20)
        scene["devices"]["1a1a1a"] = []
        links = _scene_to_array(scene)
        await ws_client.send_json(
            {
                ID: 1,
                TYPE: "insteon/scene/save",
                "scene_id": 20,
                "name": "Some scene name",
                "links": links,
            }
        )
        msg = await ws_client.receive_json()
        result = msg["result"]
        assert result["result"]
        assert result["scene_id"] == 20


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_save_new_scene(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, scene_data, remove_json
) -> None:
    """Test saving a new Insteon scene."""
    ws_client, devices = await _setup(hass, hass_ws_client, scene_data)

    mock_add_or_update_scene = AsyncMock(return_value=(21, ResponseStatus.SUCCESS))

    with patch.object(
        pyinsteon.managers.scene_manager, "devices", devices
    ), patch.object(scenes, "async_add_or_update_scene", mock_add_or_update_scene):
        scene = await pyinsteon.managers.scene_manager.async_get_scene(20)
        scene["devices"]["1a1a1a"] = []
        links = _scene_to_array(scene)
        await ws_client.send_json(
            {
                ID: 1,
                TYPE: "insteon/scene/save",
                "scene_id": -1,
                "name": "Some scene name",
                "links": links,
            }
        )
        msg = await ws_client.receive_json()
        result = msg["result"]
        assert result["result"]
        assert result["scene_id"] == 21


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_save_scene_error(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, scene_data, remove_json
) -> None:
    """Test saving an Insteon scene with error."""
    ws_client, devices = await _setup(hass, hass_ws_client, scene_data)

    mock_add_or_update_scene = AsyncMock(return_value=(20, ResponseStatus.FAILURE))

    with patch.object(
        pyinsteon.managers.scene_manager, "devices", devices
    ), patch.object(scenes, "async_add_or_update_scene", mock_add_or_update_scene):
        scene = await pyinsteon.managers.scene_manager.async_get_scene(20)
        scene["devices"]["1a1a1a"] = []
        links = _scene_to_array(scene)
        await ws_client.send_json(
            {
                ID: 1,
                TYPE: "insteon/scene/save",
                "scene_id": 20,
                "name": "Some scene name",
                "links": links,
            }
        )
        msg = await ws_client.receive_json()
        result = msg["result"]
        assert not result["result"]
        assert result["scene_id"] == 20


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_delete_scene(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, scene_data, remove_json
) -> None:
    """Test delete an Insteon scene."""
    ws_client, devices = await _setup(hass, hass_ws_client, scene_data)

    mock_delete_scene = AsyncMock(return_value=ResponseStatus.SUCCESS)

    with patch.object(
        pyinsteon.managers.scene_manager, "devices", devices
    ), patch.object(scenes, "async_delete_scene", mock_delete_scene):
        await ws_client.send_json(
            {
                ID: 1,
                TYPE: "insteon/scene/delete",
                "scene_id": 20,
            }
        )
        msg = await ws_client.receive_json()
        result = msg["result"]
        assert result["result"]
        assert result["scene_id"] == 20
