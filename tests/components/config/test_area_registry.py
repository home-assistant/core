"""Test area_registry API."""

from datetime import datetime

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_unordered import unordered

from homeassistant.components.config import area_registry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.util.dt import utcnow

from tests.common import ANY
from tests.typing import MockHAClientWebSocket, WebSocketGenerator


@pytest.fixture(name="client")
async def client_fixture(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> MockHAClientWebSocket:
    """Fixture that can interact with the config manager API."""
    area_registry.async_setup(hass)
    return await hass_ws_client(hass)


async def test_list_areas(
    client: MockHAClientWebSocket,
    area_registry: ar.AreaRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test list entries."""
    created_area1 = datetime.fromisoformat("2024-07-16T13:30:00.900075+00:00")
    freezer.move_to(created_area1)
    area1 = area_registry.async_create("mock 1")

    created_area2 = datetime.fromisoformat("2024-07-16T13:45:00.900075+00:00")
    freezer.move_to(created_area2)
    area2 = area_registry.async_create(
        "mock 2",
        aliases={"alias_1", "alias_2"},
        icon="mdi:garage",
        picture="/image/example.png",
        floor_id="first_floor",
        labels={"label_1", "label_2"},
    )

    await client.send_json_auto_id({"type": "config/area_registry/list"})

    msg = await client.receive_json()
    assert msg["result"] == [
        {
            "aliases": [],
            "area_id": area1.id,
            "floor_id": None,
            "icon": None,
            "labels": [],
            "name": "mock 1",
            "picture": None,
            "created_at": created_area1.timestamp(),
            "modified_at": created_area1.timestamp(),
        },
        {
            "aliases": unordered(["alias_1", "alias_2"]),
            "area_id": area2.id,
            "floor_id": "first_floor",
            "icon": "mdi:garage",
            "labels": unordered(["label_1", "label_2"]),
            "name": "mock 2",
            "picture": "/image/example.png",
            "created_at": created_area2.timestamp(),
            "modified_at": created_area2.timestamp(),
        },
    ]


async def test_create_area(
    client: MockHAClientWebSocket,
    area_registry: ar.AreaRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test create entry."""
    # Create area with only mandatory parameters
    await client.send_json_auto_id(
        {"name": "mock", "type": "config/area_registry/create"}
    )

    msg = await client.receive_json()

    assert msg["result"] == {
        "aliases": [],
        "area_id": ANY,
        "floor_id": None,
        "icon": None,
        "labels": [],
        "name": "mock",
        "picture": None,
        "created_at": utcnow().timestamp(),
        "modified_at": utcnow().timestamp(),
    }
    assert len(area_registry.areas) == 1

    # Create area with all parameters
    await client.send_json_auto_id(
        {
            "aliases": ["alias_1", "alias_2"],
            "floor_id": "first_floor",
            "icon": "mdi:garage",
            "labels": ["label_1", "label_2"],
            "name": "mock 2",
            "picture": "/image/example.png",
            "type": "config/area_registry/create",
        }
    )

    msg = await client.receive_json()

    assert msg["result"] == {
        "aliases": unordered(["alias_1", "alias_2"]),
        "area_id": ANY,
        "floor_id": "first_floor",
        "icon": "mdi:garage",
        "labels": unordered(["label_1", "label_2"]),
        "name": "mock 2",
        "picture": "/image/example.png",
        "created_at": utcnow().timestamp(),
        "modified_at": utcnow().timestamp(),
    }
    assert len(area_registry.areas) == 2


async def test_create_area_with_name_already_in_use(
    client: MockHAClientWebSocket, area_registry: ar.AreaRegistry
) -> None:
    """Test create entry that should fail."""
    area_registry.async_create("mock")

    await client.send_json_auto_id(
        {"name": "mock", "type": "config/area_registry/create"}
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_info"
    assert msg["error"]["message"] == "The name mock (mock) is already in use"
    assert len(area_registry.areas) == 1


async def test_delete_area(
    client: MockHAClientWebSocket, area_registry: ar.AreaRegistry
) -> None:
    """Test delete entry."""
    area = area_registry.async_create("mock")

    await client.send_json(
        {"id": 1, "area_id": area.id, "type": "config/area_registry/delete"}
    )

    msg = await client.receive_json()

    assert msg["success"]
    assert not area_registry.areas


async def test_delete_non_existing_area(
    client: MockHAClientWebSocket, area_registry: ar.AreaRegistry
) -> None:
    """Test delete entry that should fail."""
    area_registry.async_create("mock")

    await client.send_json_auto_id(
        {"area_id": "", "type": "config/area_registry/delete"}
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_info"
    assert msg["error"]["message"] == "Area ID doesn't exist"
    assert len(area_registry.areas) == 1


async def test_update_area(
    client: MockHAClientWebSocket,
    area_registry: ar.AreaRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test update entry."""
    created_at = datetime.fromisoformat("2024-07-16T13:30:00.900075+00:00")
    freezer.move_to(created_at)
    area = area_registry.async_create("mock 1")
    modified_at = datetime.fromisoformat("2024-07-16T13:45:00.900075+00:00")
    freezer.move_to(modified_at)

    await client.send_json_auto_id(
        {
            "aliases": ["alias_1", "alias_2"],
            "area_id": area.id,
            "floor_id": "first_floor",
            "icon": "mdi:garage",
            "labels": ["label_1", "label_2"],
            "name": "mock 2",
            "picture": "/image/example.png",
            "type": "config/area_registry/update",
        }
    )

    msg = await client.receive_json()

    assert msg["result"] == {
        "aliases": unordered(["alias_1", "alias_2"]),
        "area_id": area.id,
        "floor_id": "first_floor",
        "icon": "mdi:garage",
        "labels": unordered(["label_1", "label_2"]),
        "name": "mock 2",
        "picture": "/image/example.png",
        "created_at": created_at.timestamp(),
        "modified_at": modified_at.timestamp(),
    }
    assert len(area_registry.areas) == 1

    modified_at = datetime.fromisoformat("2024-07-16T13:50:00.900075+00:00")
    freezer.move_to(modified_at)

    await client.send_json_auto_id(
        {
            "aliases": ["alias_1", "alias_1"],
            "area_id": area.id,
            "floor_id": None,
            "icon": None,
            "labels": [],
            "picture": None,
            "type": "config/area_registry/update",
        }
    )

    msg = await client.receive_json()

    assert msg["result"] == {
        "aliases": ["alias_1"],
        "area_id": area.id,
        "floor_id": None,
        "icon": None,
        "labels": [],
        "name": "mock 2",
        "picture": None,
        "created_at": created_at.timestamp(),
        "modified_at": modified_at.timestamp(),
    }
    assert len(area_registry.areas) == 1


async def test_update_area_with_same_name(
    client: MockHAClientWebSocket, area_registry: ar.AreaRegistry
) -> None:
    """Test update entry."""
    area = area_registry.async_create("mock 1")

    await client.send_json_auto_id(
        {
            "area_id": area.id,
            "name": "mock 1",
            "type": "config/area_registry/update",
        }
    )

    msg = await client.receive_json()

    assert msg["result"]["area_id"] == area.id
    assert msg["result"]["name"] == "mock 1"
    assert len(area_registry.areas) == 1


async def test_update_area_with_name_already_in_use(
    client: MockHAClientWebSocket, area_registry: ar.AreaRegistry
) -> None:
    """Test update entry."""
    area = area_registry.async_create("mock 1")
    area_registry.async_create("mock 2")

    await client.send_json_auto_id(
        {
            "area_id": area.id,
            "name": "mock 2",
            "type": "config/area_registry/update",
        }
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_info"
    assert msg["error"]["message"] == "The name mock 2 (mock2) is already in use"
    assert len(area_registry.areas) == 2
