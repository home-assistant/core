"""Test the Insteon Scenes APIs."""

from collections.abc import Generator
import os
from typing import Any
from unittest.mock import AsyncMock, patch

from pyinsteon.constants import ResponseStatus
from pyinsteon.managers.scene_controller_manager import SceneControllerError
import pyinsteon.managers.scene_manager
import pytest

from homeassistant.components.insteon.api import async_load_api, scenes
from homeassistant.components.insteon.const import ID, TYPE
from homeassistant.core import HomeAssistant
from homeassistant.util.json import JsonArrayType

from .mock_devices import MockDevices

from tests.common import load_json_array_fixture
from tests.typing import MockHAClientWebSocket, WebSocketGenerator


@pytest.fixture(name="scene_data", scope="module")
def aldb_data_fixture() -> JsonArrayType:
    """Load the controller state fixture data."""
    return load_json_array_fixture("insteon/scene_data.json")


@pytest.fixture(name="remove_json")
def remove_insteon_devices_json(hass: HomeAssistant) -> Generator[None]:
    """Fixture to remove insteon_devices.json at the end of the test."""
    yield
    file = os.path.join(hass.config.config_dir, "insteon_devices.json")
    if os.path.exists(file):
        os.remove(file)


def _scene_to_array(scene: dict[str, Any]) -> list[dict[str, Any]]:
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


async def _setup(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, scene_data: JsonArrayType
) -> tuple[MockHAClientWebSocket, MockDevices]:
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


async def test_get_scenes(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, scene_data: JsonArrayType
) -> None:
    """Test getting all Insteon scenes."""
    ws_client, devices = await _setup(hass, hass_ws_client, scene_data)

    with patch.object(pyinsteon.managers.scene_manager, "devices", devices):
        await ws_client.send_json({ID: 1, TYPE: "insteon/scenes/get"})
        msg = await ws_client.receive_json()
        result = msg["result"]
        assert len(result) == 1
        assert result["20"]["controllers"] == []
        assert result["20"]["pending"] is False


async def test_get_scene(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, scene_data: JsonArrayType
) -> None:
    """Test getting an Insteon scene."""
    ws_client, devices = await _setup(hass, hass_ws_client, scene_data)

    with patch.object(pyinsteon.managers.scene_manager, "devices", devices):
        await ws_client.send_json({ID: 1, TYPE: "insteon/scene/get", "scene_id": 20})
        msg = await ws_client.receive_json()
        result = msg["result"]
        assert len(result["devices"]) == 3


@pytest.mark.usefixtures("remove_json")
async def test_save_scene(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    scene_data: JsonArrayType,
) -> None:
    """Test saving an Insteon scene."""
    ws_client, devices = await _setup(hass, hass_ws_client, scene_data)

    mock_add_or_update_scene = AsyncMock(return_value=(20, ResponseStatus.SUCCESS))

    with (
        patch.object(pyinsteon.managers.scene_manager, "devices", devices),
        patch.object(scenes, "async_add_or_update_scene", mock_add_or_update_scene),
    ):
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


@pytest.mark.usefixtures("remove_json")
async def test_save_new_scene(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    scene_data: JsonArrayType,
) -> None:
    """Test saving a new Insteon scene."""
    ws_client, devices = await _setup(hass, hass_ws_client, scene_data)

    mock_add_or_update_scene = AsyncMock(return_value=(21, ResponseStatus.SUCCESS))

    with (
        patch.object(pyinsteon.managers.scene_manager, "devices", devices),
        patch.object(scenes, "async_add_or_update_scene", mock_add_or_update_scene),
    ):
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


@pytest.mark.usefixtures("remove_json")
async def test_save_scene_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    scene_data: JsonArrayType,
) -> None:
    """Test saving an Insteon scene with error."""
    ws_client, devices = await _setup(hass, hass_ws_client, scene_data)

    mock_add_or_update_scene = AsyncMock(return_value=(20, ResponseStatus.FAILURE))

    with (
        patch.object(pyinsteon.managers.scene_manager, "devices", devices),
        patch.object(scenes, "async_add_or_update_scene", mock_add_or_update_scene),
    ):
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


@pytest.mark.usefixtures("remove_json")
async def test_delete_scene(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    scene_data: JsonArrayType,
) -> None:
    """Test delete an Insteon scene."""
    ws_client, devices = await _setup(hass, hass_ws_client, scene_data)

    mock_delete_scene = AsyncMock(return_value=ResponseStatus.SUCCESS)

    with (
        patch.object(pyinsteon.managers.scene_manager, "devices", devices),
        patch.object(scenes, "async_delete_scene", mock_delete_scene),
    ):
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


@pytest.mark.parametrize(
    ("payload", "controllers"),
    [
        pytest.param({}, None, id="omitted-preserves-controllers"),
        pytest.param({"controllers": []}, [], id="empty-removes-controllers"),
        pytest.param(
            {"controllers": [{"address": "33.33.33", "group": 3}]},
            [{"address": "33.33.33", "group": 3}],
            id="hardware-button",
        ),
    ],
)
async def test_save_scene_controllers(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    payload: dict[str, object],
    controllers: list[dict[str, str | int]] | None,
) -> None:
    """Forward controller selections without changing their group numbers."""
    ws_client = await hass_ws_client(hass)
    async_load_api(hass)
    save = AsyncMock(return_value=(20, ResponseStatus.SUCCESS))
    with (
        patch.object(scenes, "async_add_or_update_scene", save),
        patch.object(scenes.devices, "async_save"),
    ):
        await ws_client.send_json(
            {
                ID: 1,
                TYPE: "insteon/scene/save",
                "scene_id": 20,
                "name": "Evening",
                "links": [],
                **payload,
            }
        )
        msg = await ws_client.receive_json()
    assert msg["result"] == {"scene_id": 20, "result": True}
    save.assert_awaited_once_with(
        scene_num=20,
        links=[],
        name="Evening",
        work_dir=hass.config.config_dir,
        controllers=controllers,
    )


async def test_get_scene_controllers(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Expose the logical scene association and interrupted-write status."""
    ws_client = await hass_ws_client(hass)
    async_load_api(hass)
    scene = {
        "name": "Evening",
        "group": 20,
        "devices": {},
        "controllers": [{"address": "33.33.33", "group": 3}],
        "pending": True,
    }
    with patch.object(scenes, "async_get_scene", AsyncMock(return_value=scene)):
        await ws_client.send_json({ID: 1, TYPE: "insteon/scene/get", "scene_id": 20})
        msg = await ws_client.receive_json()
    assert msg["result"] == scene


@pytest.mark.parametrize(
    ("command", "function", "payload"),
    [
        pytest.param(
            "save",
            "async_add_or_update_scene",
            {"name": "Evening", "links": []},
            id="save-conflict",
        ),
        pytest.param("delete", "async_delete_scene", {}, id="delete-missing-device"),
        pytest.param("get", "async_get_scene", {}, id="get-corrupt-metadata"),
    ],
)
async def test_scene_controller_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    command: str,
    function: str,
    payload: dict[str, object],
) -> None:
    """Return actionable scene errors without reporting success."""
    ws_client = await hass_ws_client(hass)
    async_load_api(hass)
    with patch.object(
        scenes,
        function,
        AsyncMock(
            side_effect=SceneControllerError("Controller group is already in use")
        ),
    ):
        await ws_client.send_json(
            {ID: 1, TYPE: f"insteon/scene/{command}", "scene_id": 20, **payload}
        )
        msg = await ws_client.receive_json()
    assert msg["success"] is False
    assert msg["error"] == {
        "code": "scene_error",
        "message": "Controller group is already in use",
    }


@pytest.mark.parametrize("group", [0, 256])
async def test_invalid_controller_group(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, group: int
) -> None:
    """Reject controller groups outside the one-byte hardware range."""
    ws_client = await hass_ws_client(hass)
    async_load_api(hass)
    save = AsyncMock()
    with patch.object(scenes, "async_add_or_update_scene", save):
        await ws_client.send_json(
            {
                ID: 1,
                TYPE: "insteon/scene/save",
                "scene_id": 20,
                "name": "Evening",
                "links": [],
                "controllers": [{"address": "33.33.33", "group": group}],
            }
        )
        msg = await ws_client.receive_json()
    assert msg["success"] is False
    assert msg["error"]["code"] == "invalid_format"
    save.assert_not_awaited()


DEVICE_SCENE = {
    "controllers": [{"address": "333333", "group": 3}],
    "links": [{"address": "444444", "data1": 128, "data2": 28, "data3": 1}],
    "issues": [],
    "importable": True,
}


async def test_get_device_scenes(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """List hand-made device scenes that can be imported."""
    ws_client = await hass_ws_client(hass)
    async_load_api(hass)
    find = AsyncMock(return_value=[DEVICE_SCENE])
    with patch.object(scenes, "async_find_device_scenes", find):
        await ws_client.send_json({ID: 1, TYPE: "insteon/scenes/device_scenes"})
        msg = await ws_client.receive_json()
    assert msg["result"] == [DEVICE_SCENE]
    find.assert_awaited_once_with(work_dir=hass.config.config_dir)


@pytest.mark.parametrize("status", [ResponseStatus.SUCCESS, ResponseStatus.FAILURE])
async def test_import_scene(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, status: ResponseStatus
) -> None:
    """Import a device scene under a new modem group."""
    ws_client = await hass_ws_client(hass)
    async_load_api(hass)
    import_scene = AsyncMock(return_value=(21, status))
    with (
        patch.object(scenes, "async_import_device_scene", import_scene),
        patch.object(scenes.devices, "async_save") as save,
    ):
        await ws_client.send_json(
            {
                ID: 1,
                TYPE: "insteon/scene/import",
                "name": "Evening",
                "controllers": DEVICE_SCENE["controllers"],
            }
        )
        msg = await ws_client.receive_json()
    assert msg["result"] == {
        "scene_id": 21,
        "result": status == ResponseStatus.SUCCESS,
    }
    import_scene.assert_awaited_once_with(
        controllers=DEVICE_SCENE["controllers"],
        name="Evening",
        work_dir=hass.config.config_dir,
    )
    save.assert_awaited_once()


@pytest.mark.parametrize(
    ("command", "function", "payload"),
    [
        pytest.param(
            "scenes/device_scenes",
            "async_find_device_scenes",
            {},
            id="list-corrupt-metadata",
        ),
        pytest.param(
            "scene/import",
            "async_import_device_scene",
            {"name": "Evening", "controllers": DEVICE_SCENE["controllers"]},
            id="import-blocked",
        ),
    ],
)
async def test_device_scene_errors(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    command: str,
    function: str,
    payload: dict[str, object],
) -> None:
    """Return actionable errors when device scenes cannot be listed or imported."""
    ws_client = await hass_ws_client(hass)
    async_load_api(hass)
    with patch.object(
        scenes,
        function,
        AsyncMock(side_effect=SceneControllerError("Read the database")),
    ):
        await ws_client.send_json({ID: 1, TYPE: f"insteon/{command}", **payload})
        msg = await ws_client.receive_json()
    assert msg["success"] is False
    assert msg["error"] == {"code": "scene_error", "message": "Read the database"}
