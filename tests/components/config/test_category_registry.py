"""Test category registry API."""

from datetime import datetime

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.config import category_registry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import category_registry as cr
from homeassistant.util.dt import utcnow

from tests.common import ANY
from tests.typing import MockHAClientWebSocket, WebSocketGenerator


@pytest.fixture(name="client")
async def client_fixture(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> MockHAClientWebSocket:
    """Fixture that can interact with the config manager API."""
    category_registry.async_setup(hass)
    return await hass_ws_client(hass)


@pytest.mark.usefixtures("freezer")
async def test_list_categories(
    client: MockHAClientWebSocket,
    category_registry: cr.CategoryRegistry,
) -> None:
    """Test list entries."""
    category1 = category_registry.async_create(
        scope="automation",
        name="Energy saving",
        icon="mdi:leaf",
    )
    category2 = category_registry.async_create(
        scope="automation",
        name="Something else",
        icon="mdi:home",
    )
    category3 = category_registry.async_create(
        scope="zone",
        name="Grocery stores",
        icon="mdi:store",
    )

    assert len(category_registry.categories) == 2
    assert len(category_registry.categories["automation"]) == 2
    assert len(category_registry.categories["zone"]) == 1

    await client.send_json_auto_id(
        {"type": "config/category_registry/list", "scope": "automation"}
    )

    msg = await client.receive_json()

    assert len(msg["result"]) == 2
    assert msg["result"][0] == {
        "category_id": category1.category_id,
        "created_at": utcnow().timestamp(),
        "modified_at": utcnow().timestamp(),
        "name": "Energy saving",
        "icon": "mdi:leaf",
    }
    assert msg["result"][1] == {
        "category_id": category2.category_id,
        "created_at": utcnow().timestamp(),
        "modified_at": utcnow().timestamp(),
        "name": "Something else",
        "icon": "mdi:home",
    }

    await client.send_json_auto_id(
        {"type": "config/category_registry/list", "scope": "zone"}
    )

    msg = await client.receive_json()

    assert len(msg["result"]) == 1
    assert msg["result"][0] == {
        "category_id": category3.category_id,
        "created_at": utcnow().timestamp(),
        "modified_at": utcnow().timestamp(),
        "name": "Grocery stores",
        "icon": "mdi:store",
    }


async def test_create_category(
    client: MockHAClientWebSocket,
    category_registry: cr.CategoryRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test create entry."""
    created1 = datetime(2024, 2, 14, 12, 0, 0)
    freezer.move_to(created1)
    await client.send_json_auto_id(
        {
            "type": "config/category_registry/create",
            "scope": "automation",
            "name": "Energy saving",
            "icon": "mdi:leaf",
        }
    )

    msg = await client.receive_json()

    assert len(category_registry.categories) == 1
    assert len(category_registry.categories["automation"]) == 1

    assert msg["result"] == {
        "icon": "mdi:leaf",
        "category_id": ANY,
        "created_at": created1.timestamp(),
        "modified_at": created1.timestamp(),
        "name": "Energy saving",
    }

    created2 = datetime(2024, 3, 14, 12, 0, 0)
    freezer.move_to(created2)

    await client.send_json_auto_id(
        {
            "scope": "automation",
            "name": "Something else",
            "type": "config/category_registry/create",
        }
    )

    msg = await client.receive_json()

    assert len(category_registry.categories) == 1
    assert len(category_registry.categories["automation"]) == 2

    assert msg["result"] == {
        "icon": None,
        "category_id": ANY,
        "created_at": created2.timestamp(),
        "modified_at": created2.timestamp(),
        "name": "Something else",
    }

    created3 = datetime(2024, 4, 14, 12, 0, 0)
    freezer.move_to(created3)

    # Test adding the same one again in a different scope
    await client.send_json_auto_id(
        {
            "type": "config/category_registry/create",
            "scope": "script",
            "name": "Energy saving",
            "icon": "mdi:leaf",
        }
    )

    msg = await client.receive_json()

    assert len(category_registry.categories) == 2
    assert len(category_registry.categories["automation"]) == 2
    assert len(category_registry.categories["script"]) == 1

    assert msg["result"] == {
        "icon": "mdi:leaf",
        "category_id": ANY,
        "created_at": created3.timestamp(),
        "modified_at": created3.timestamp(),
        "name": "Energy saving",
    }


async def test_create_category_with_name_already_in_use(
    client: MockHAClientWebSocket,
    category_registry: cr.CategoryRegistry,
) -> None:
    """Test create entry that should fail."""
    category_registry.async_create(
        scope="automation",
        name="Energy saving",
    )
    assert len(category_registry.categories) == 1
    assert len(category_registry.categories["automation"]) == 1

    await client.send_json_auto_id(
        {
            "scope": "automation",
            "name": "ENERGY SAVING",
            "type": "config/category_registry/create",
        }
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_info"
    assert msg["error"]["message"] == "The name 'ENERGY SAVING' is already in use"
    assert len(category_registry.categories) == 1
    assert len(category_registry.categories["automation"]) == 1


async def test_delete_category(
    client: MockHAClientWebSocket,
    category_registry: cr.CategoryRegistry,
) -> None:
    """Test delete entry."""
    category = category_registry.async_create(
        scope="automation",
        name="Energy saving",
        icon="mdi:leaf",
    )
    assert len(category_registry.categories) == 1
    assert len(category_registry.categories["automation"]) == 1

    await client.send_json_auto_id(
        {
            "scope": "automation",
            "category_id": category.category_id,
            "type": "config/category_registry/delete",
        }
    )

    msg = await client.receive_json()

    assert msg["success"]
    assert len(category_registry.categories) == 1
    assert not category_registry.categories["automation"]


async def test_delete_non_existing_category(
    client: MockHAClientWebSocket,
    category_registry: cr.CategoryRegistry,
) -> None:
    """Test delete entry that should fail."""
    category = category_registry.async_create(
        scope="automation",
        name="Energy saving",
        icon="mdi:leaf",
    )
    assert len(category_registry.categories) == 1
    assert len(category_registry.categories["automation"]) == 1

    await client.send_json_auto_id(
        {
            "scope": "automation",
            "category_id": "idkfa",
            "type": "config/category_registry/delete",
        }
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_info"
    assert msg["error"]["message"] == "Category ID doesn't exist"
    assert len(category_registry.categories) == 1
    assert len(category_registry.categories["automation"]) == 1

    await client.send_json_auto_id(
        {
            "scope": "bullshizzle",
            "category_id": category.category_id,
            "type": "config/category_registry/delete",
        }
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_info"
    assert msg["error"]["message"] == "Category ID doesn't exist"
    assert len(category_registry.categories) == 1
    assert len(category_registry.categories["automation"]) == 1


async def test_update_category(
    client: MockHAClientWebSocket,
    category_registry: cr.CategoryRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test update entry."""
    created = datetime(2024, 2, 14, 12, 0, 0)
    freezer.move_to(created)
    category = category_registry.async_create(
        scope="automation",
        name="Energy saving",
    )
    assert len(category_registry.categories) == 1
    assert len(category_registry.categories["automation"]) == 1

    modified = datetime(2024, 3, 14, 12, 0, 0)
    freezer.move_to(modified)

    await client.send_json_auto_id(
        {
            "scope": "automation",
            "category_id": category.category_id,
            "name": "ENERGY SAVING",
            "icon": "mdi:left",
            "type": "config/category_registry/update",
        }
    )

    msg = await client.receive_json()

    assert len(category_registry.categories) == 1
    assert len(category_registry.categories["automation"]) == 1
    assert msg["result"] == {
        "icon": "mdi:left",
        "category_id": category.category_id,
        "created_at": created.timestamp(),
        "modified_at": modified.timestamp(),
        "name": "ENERGY SAVING",
    }

    modified = datetime(2024, 4, 14, 12, 0, 0)
    freezer.move_to(modified)

    await client.send_json_auto_id(
        {
            "scope": "automation",
            "category_id": category.category_id,
            "name": "Energy saving",
            "icon": None,
            "type": "config/category_registry/update",
        }
    )

    msg = await client.receive_json()

    assert len(category_registry.categories) == 1
    assert len(category_registry.categories["automation"]) == 1
    assert msg["result"] == {
        "icon": None,
        "category_id": category.category_id,
        "created_at": created.timestamp(),
        "modified_at": modified.timestamp(),
        "name": "Energy saving",
    }


async def test_update_with_name_already_in_use(
    client: MockHAClientWebSocket,
    category_registry: cr.CategoryRegistry,
) -> None:
    """Test update entry."""
    category_registry.async_create(
        scope="automation",
        name="Energy saving",
    )
    category = category_registry.async_create(
        scope="automation",
        name="Something else",
    )
    assert len(category_registry.categories) == 1
    assert len(category_registry.categories["automation"]) == 2

    await client.send_json_auto_id(
        {
            "scope": "automation",
            "category_id": category.category_id,
            "name": "ENERGY SAVING",
            "type": "config/category_registry/update",
        }
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_info"
    assert msg["error"]["message"] == "The name 'ENERGY SAVING' is already in use"
    assert len(category_registry.categories) == 1
    assert len(category_registry.categories["automation"]) == 2


async def test_update_non_existing_category(
    client: MockHAClientWebSocket,
    category_registry: cr.CategoryRegistry,
) -> None:
    """Test update entry that should fail."""
    category = category_registry.async_create(
        scope="automation",
        name="Energy saving",
        icon="mdi:leaf",
    )
    assert len(category_registry.categories) == 1
    assert len(category_registry.categories["automation"]) == 1

    await client.send_json_auto_id(
        {
            "scope": "automation",
            "category_id": "idkfa",
            "name": "New category name",
            "type": "config/category_registry/update",
        }
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_info"
    assert msg["error"]["message"] == "Category ID doesn't exist"
    assert len(category_registry.categories) == 1
    assert len(category_registry.categories["automation"]) == 1

    await client.send_json_auto_id(
        {
            "scope": "bullshizzle",
            "category_id": category.category_id,
            "name": "New category name",
            "type": "config/category_registry/update",
        }
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_info"
    assert msg["error"]["message"] == "Category ID doesn't exist"
    assert len(category_registry.categories) == 1
    assert len(category_registry.categories["automation"]) == 1
