"""Test area_registry API."""
import pytest
from pytest_unordered import unordered

from homeassistant.components.config import area_registry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar

from tests.common import ANY


@pytest.fixture
def client(hass, hass_ws_client):
    """Fixture that can interact with the config manager API."""
    hass.loop.run_until_complete(area_registry.async_setup(hass))
    return hass.loop.run_until_complete(hass_ws_client(hass))


async def test_list_areas(
    hass: HomeAssistant, client, area_registry: ar.AreaRegistry
) -> None:
    """Test list entries."""
    area1 = area_registry.async_create("mock 1")
    area2 = area_registry.async_create(
        "mock 2", aliases={"alias_1", "alias_2"}, picture="/image/example.png"
    )

    await client.send_json({"id": 1, "type": "config/area_registry/list"})

    msg = await client.receive_json()
    assert msg["result"] == [
        {
            "aliases": [],
            "area_id": area1.id,
            "name": "mock 1",
            "picture": None,
        },
        {
            "aliases": unordered(["alias_1", "alias_2"]),
            "area_id": area2.id,
            "name": "mock 2",
            "picture": "/image/example.png",
        },
    ]


async def test_create_area(
    hass: HomeAssistant, client, area_registry: ar.AreaRegistry
) -> None:
    """Test create entry."""
    # Create area with only mandatory parameters
    await client.send_json(
        {"id": 1, "name": "mock", "type": "config/area_registry/create"}
    )

    msg = await client.receive_json()

    assert msg["result"] == {
        "aliases": [],
        "area_id": ANY,
        "name": "mock",
        "picture": None,
    }
    assert len(area_registry.areas) == 1

    # Create area with all parameters
    await client.send_json(
        {
            "id": 2,
            "aliases": ["alias_1", "alias_2"],
            "name": "mock 2",
            "picture": "/image/example.png",
            "type": "config/area_registry/create",
        }
    )

    msg = await client.receive_json()

    assert msg["result"] == {
        "aliases": unordered(["alias_1", "alias_2"]),
        "area_id": ANY,
        "name": "mock 2",
        "picture": "/image/example.png",
    }
    assert len(area_registry.areas) == 2


async def test_create_area_with_name_already_in_use(
    hass: HomeAssistant, client, area_registry: ar.AreaRegistry
) -> None:
    """Test create entry that should fail."""
    area_registry.async_create("mock")

    await client.send_json(
        {"id": 1, "name": "mock", "type": "config/area_registry/create"}
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_info"
    assert msg["error"]["message"] == "The name mock (mock) is already in use"
    assert len(area_registry.areas) == 1


async def test_delete_area(
    hass: HomeAssistant, client, area_registry: ar.AreaRegistry
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
    hass: HomeAssistant, client, area_registry: ar.AreaRegistry
) -> None:
    """Test delete entry that should fail."""
    area_registry.async_create("mock")

    await client.send_json(
        {"id": 1, "area_id": "", "type": "config/area_registry/delete"}
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_info"
    assert msg["error"]["message"] == "Area ID doesn't exist"
    assert len(area_registry.areas) == 1


async def test_update_area(
    hass: HomeAssistant, client, area_registry: ar.AreaRegistry
) -> None:
    """Test update entry."""
    area = area_registry.async_create("mock 1")

    await client.send_json(
        {
            "id": 1,
            "aliases": ["alias_1", "alias_2"],
            "area_id": area.id,
            "name": "mock 2",
            "picture": "/image/example.png",
            "type": "config/area_registry/update",
        }
    )

    msg = await client.receive_json()

    assert msg["result"] == {
        "aliases": unordered(["alias_1", "alias_2"]),
        "area_id": area.id,
        "name": "mock 2",
        "picture": "/image/example.png",
    }
    assert len(area_registry.areas) == 1

    await client.send_json(
        {
            "id": 2,
            "aliases": ["alias_1", "alias_1"],
            "area_id": area.id,
            "picture": None,
            "type": "config/area_registry/update",
        }
    )

    msg = await client.receive_json()

    assert msg["result"] == {
        "aliases": ["alias_1"],
        "area_id": area.id,
        "name": "mock 2",
        "picture": None,
    }
    assert len(area_registry.areas) == 1


async def test_update_area_with_same_name(
    hass: HomeAssistant, client, area_registry: ar.AreaRegistry
) -> None:
    """Test update entry."""
    area = area_registry.async_create("mock 1")

    await client.send_json(
        {
            "id": 1,
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
    hass: HomeAssistant, client, area_registry: ar.AreaRegistry
) -> None:
    """Test update entry."""
    area = area_registry.async_create("mock 1")
    area_registry.async_create("mock 2")

    await client.send_json(
        {
            "id": 1,
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
