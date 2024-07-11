"""Test floor registry API."""

import pytest
from pytest_unordered import unordered

from homeassistant.components.config import floor_registry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import floor_registry as fr

from tests.typing import MockHAClientWebSocket, WebSocketGenerator


@pytest.fixture(name="client")
async def client_fixture(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> MockHAClientWebSocket:
    """Fixture that can interact with the config manager API."""
    floor_registry.async_setup(hass)
    return await hass_ws_client(hass)


async def test_list_floors(
    client: MockHAClientWebSocket,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test list entries."""
    floor_registry.async_create("First floor")
    floor_registry.async_create(
        name="Second floor",
        aliases={"top floor", "attic"},
        icon="mdi:home-floor-2",
        level=2,
    )

    assert len(floor_registry.floors) == 2

    await client.send_json_auto_id({"type": "config/floor_registry/list"})

    msg = await client.receive_json()

    assert len(msg["result"]) == len(floor_registry.floors)
    assert msg["result"][0] == {
        "aliases": [],
        "icon": None,
        "floor_id": "first_floor",
        "name": "First floor",
        "level": None,
    }
    assert msg["result"][1] == {
        "aliases": unordered(["top floor", "attic"]),
        "icon": "mdi:home-floor-2",
        "floor_id": "second_floor",
        "name": "Second floor",
        "level": 2,
    }


async def test_create_floor(
    client: MockHAClientWebSocket,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test create entry."""
    await client.send_json_auto_id(
        {"type": "config/floor_registry/create", "name": "First floor"}
    )

    msg = await client.receive_json()

    assert len(floor_registry.floors) == 1
    assert msg["result"] == {
        "aliases": [],
        "icon": None,
        "floor_id": "first_floor",
        "name": "First floor",
        "level": None,
    }

    await client.send_json_auto_id(
        {
            "name": "Second floor",
            "type": "config/floor_registry/create",
            "aliases": ["top floor", "attic"],
            "icon": "mdi:home-floor-2",
            "level": 2,
        }
    )

    msg = await client.receive_json()

    assert len(floor_registry.floors) == 2
    assert msg["result"] == {
        "aliases": unordered(["top floor", "attic"]),
        "icon": "mdi:home-floor-2",
        "floor_id": "second_floor",
        "name": "Second floor",
        "level": 2,
    }


async def test_create_floor_with_name_already_in_use(
    client: MockHAClientWebSocket,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test create entry that should fail."""
    floor_registry.async_create("First floor")
    assert len(floor_registry.floors) == 1

    await client.send_json_auto_id(
        {"name": "First floor", "type": "config/floor_registry/create"}
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_info"
    assert (
        msg["error"]["message"] == "The name First floor (firstfloor) is already in use"
    )
    assert len(floor_registry.floors) == 1


async def test_delete_floor(
    client: MockHAClientWebSocket,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test delete entry."""
    floor = floor_registry.async_create("First floor")
    assert len(floor_registry.floors) == 1

    await client.send_json_auto_id(
        {"floor_id": floor.floor_id, "type": "config/floor_registry/delete"}
    )

    msg = await client.receive_json()

    assert msg["success"]
    assert not floor_registry.floors


async def test_delete_non_existing_floor(
    client: MockHAClientWebSocket,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test delete entry that should fail."""
    floor_registry.async_create("First floor")
    assert len(floor_registry.floors) == 1

    await client.send_json_auto_id(
        {
            "floor_id": "zaphotbeeblebrox",
            "type": "config/floor_registry/delete",
        }
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_info"
    assert msg["error"]["message"] == "Floor ID doesn't exist"
    assert len(floor_registry.floors) == 1


async def test_update_floor(
    client: MockHAClientWebSocket,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test update entry."""
    floor = floor_registry.async_create("First floor")
    assert len(floor_registry.floors) == 1

    await client.send_json_auto_id(
        {
            "floor_id": floor.floor_id,
            "name": "Second floor",
            "aliases": ["top floor", "attic"],
            "icon": "mdi:home-floor-2",
            "type": "config/floor_registry/update",
            "level": 2,
        }
    )

    msg = await client.receive_json()

    assert len(floor_registry.floors) == 1
    assert msg["result"] == {
        "aliases": unordered(["top floor", "attic"]),
        "icon": "mdi:home-floor-2",
        "floor_id": floor.floor_id,
        "name": "Second floor",
        "level": 2,
    }

    await client.send_json_auto_id(
        {
            "floor_id": floor.floor_id,
            "name": "First floor",
            "aliases": [],
            "icon": None,
            "level": None,
            "type": "config/floor_registry/update",
        }
    )

    msg = await client.receive_json()

    assert len(floor_registry.floors) == 1
    assert msg["result"] == {
        "aliases": [],
        "icon": None,
        "floor_id": floor.floor_id,
        "name": "First floor",
        "level": None,
    }


async def test_update_with_name_already_in_use(
    client: MockHAClientWebSocket,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test update entry."""
    floor = floor_registry.async_create("First floor")
    floor_registry.async_create("Second floor")
    assert len(floor_registry.floors) == 2

    await client.send_json_auto_id(
        {
            "floor_id": floor.floor_id,
            "name": "Second floor",
            "type": "config/floor_registry/update",
        }
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_info"
    assert (
        msg["error"]["message"]
        == "The name Second floor (secondfloor) is already in use"
    )
    assert len(floor_registry.floors) == 2
