"""Test folder registry API."""
from collections.abc import Awaitable, Callable, Generator
from typing import Any

from aiohttp import ClientWebSocketResponse
import pytest

from homeassistant.components.config import folder_registry as config_folder_registry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import folder_registry as fr

from tests.common import ANY


@pytest.fixture(name="client")
def client_fixture(
    hass: HomeAssistant,
    hass_ws_client: Callable[
        [HomeAssistant], Awaitable[Generator[ClientWebSocketResponse, Any, Any]]
    ],
) -> Generator[ClientWebSocketResponse, None, None]:
    """Fixture that can interact with the config manager API."""
    hass.loop.run_until_complete(config_folder_registry.async_setup(hass))
    return hass.loop.run_until_complete(hass_ws_client(hass))


@pytest.mark.usefixtures("hass")
async def test_list_folders(
    client: ClientWebSocketResponse,
    folder_registry: fr.FolderRegistry,
) -> None:
    """Test list entries."""
    folder_registry.async_create("automation", "mock 1")
    folder_registry.async_create(
        domain="automation",
        name="mock 2",
        icon="mdi:two",
    )

    assert len(folder_registry.folders) == 2

    await client.send_json(
        {"id": 1, "type": "config/folder_registry/list", "domain": "automation"}
    )

    msg = await client.receive_json()

    assert len(msg["result"]) == len(folder_registry.folders)
    assert msg["result"][0] == {
        "folder_id": ANY,
        "icon": None,
        "name": "mock 1",
    }
    assert msg["result"][1] == {
        "folder_id": ANY,
        "icon": "mdi:two",
        "name": "mock 2",
    }


@pytest.mark.usefixtures("hass")
async def test_create_folder(
    client: ClientWebSocketResponse,
    folder_registry: fr.FolderRegistry,
) -> None:
    """Test create entry."""
    await client.send_json(
        {
            "id": 1,
            "type": "config/folder_registry/create",
            "domain": "automation",
            "name": "Bedroom",
        }
    )

    msg = await client.receive_json()

    assert len(folder_registry.folders) == 1
    assert msg["result"] == {
        "folder_id": ANY,
        "icon": None,
        "name": "Bedroom",
    }

    await client.send_json(
        {
            "id": 2,
            "type": "config/folder_registry/create",
            "domain": "automation",
            "name": "Kitchen",
            "icon": "mdi:kitchen",
        }
    )

    msg = await client.receive_json()

    assert len(folder_registry.folders) == 2
    assert msg["result"] == {
        "folder_id": ANY,
        "icon": "mdi:kitchen",
        "name": "Kitchen",
    }


@pytest.mark.usefixtures("hass")
async def test_create_folder_with_name_already_in_use(
    client: ClientWebSocketResponse,
    folder_registry: fr.FolderRegistry,
) -> None:
    """Test create entry that should fail."""
    folder_registry.async_create("automation", "Garden")
    assert len(folder_registry.folders) == 1

    await client.send_json(
        {
            "id": 1,
            "type": "config/folder_registry/create",
            "domain": "automation",
            "name": "garden",
        }
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_info"
    assert msg["error"]["message"] == "The name garden (garden) is already in use"
    assert len(folder_registry.folders) == 1


@pytest.mark.usefixtures("hass")
async def test_delete_folder(
    client: ClientWebSocketResponse,
    folder_registry: fr.FolderRegistry,
) -> None:
    """Test delete entry."""
    folder = folder_registry.async_create("automation", "Mancave")
    assert len(folder_registry.folders) == 1

    await client.send_json(
        {
            "id": 1,
            "folder_id": folder.folder_id,
            "type": "config/folder_registry/delete",
        }
    )

    msg = await client.receive_json()

    assert msg["success"]
    assert not folder_registry.folders


@pytest.mark.usefixtures("hass")
async def test_delete_non_existing_folder(
    client: ClientWebSocketResponse,
    folder_registry: fr.FolderRegistry,
) -> None:
    """Test delete entry that should fail."""
    folder_registry.async_create("automation", "Garage")
    assert len(folder_registry.folders) == 1

    await client.send_json(
        {"id": 1, "folder_id": "omg_puppies", "type": "config/folder_registry/delete"}
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_info"
    assert msg["error"]["message"] == "Folder ID doesn't exist"
    assert len(folder_registry.folders) == 1


@pytest.mark.usefixtures("hass")
async def test_update_folder(
    client: ClientWebSocketResponse,
    folder_registry: fr.FolderRegistry,
) -> None:
    """Test update entry."""
    folder = folder_registry.async_create("automation", "Office")
    assert len(folder_registry.folders) == 1

    await client.send_json(
        {
            "id": 1,
            "type": "config/folder_registry/update",
            "folder_id": folder.folder_id,
            "name": "Baby's Room",
            "icon": "mdi:baby",
        }
    )

    msg = await client.receive_json()

    assert len(folder_registry.folders) == 1
    assert msg["result"] == {
        "folder_id": folder.folder_id,
        "icon": "mdi:baby",
        "name": "Baby's Room",
    }

    await client.send_json(
        {
            "id": 2,
            "type": "config/folder_registry/update",
            "folder_id": folder.folder_id,
            "name": "Todler's Room",
            "icon": None,
        }
    )

    msg = await client.receive_json()

    assert len(folder_registry.folders) == 1
    assert msg["result"] == {
        "icon": None,
        "folder_id": folder.folder_id,
        "name": "Todler's Room",
    }


@pytest.mark.usefixtures("hass")
async def test_update_with_name_already_in_use(
    client: ClientWebSocketResponse,
    folder_registry: fr.FolderRegistry,
) -> None:
    """Test update entry."""
    folder = folder_registry.async_create("automation", "Notifications")
    folder_registry.async_create("automation", "Living room")
    assert len(folder_registry.folders) == 2

    await client.send_json(
        {
            "id": 1,
            "folder_id": folder.folder_id,
            "name": "Living room",
            "type": "config/folder_registry/update",
        }
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_info"
    assert (
        msg["error"]["message"] == "The name Living room (livingroom) is already in use"
    )
    assert len(folder_registry.folders) == 2
