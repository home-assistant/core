"""Test label registry API."""

from datetime import datetime

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.config import label_registry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import label_registry as lr

from tests.typing import MockHAClientWebSocket, WebSocketGenerator


@pytest.fixture(name="client")
async def client_fixture(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> MockHAClientWebSocket:
    """Fixture that can interact with the config manager API."""
    label_registry.async_setup(hass)
    return await hass_ws_client(hass)


async def test_list_labels(
    client: MockHAClientWebSocket,
    label_registry: lr.LabelRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test list entries."""
    created_1 = datetime.fromisoformat("2024-07-16T13:30:00.900075+00:00")
    freezer.move_to(created_1)
    label_registry.async_create("mock 1")

    created_2 = datetime.fromisoformat("2024-07-16T13:45:00.900075+00:00")
    freezer.move_to(created_2)
    label_registry.async_create(
        name="mock 2",
        color="#00FF00",
        icon="mdi:two",
        description="This is the second label",
    )

    assert len(label_registry.labels) == 2

    # update mock 1 to change modified_at
    label_registry.async_update(
        "mock_1",
        name="Mock 1...",
    )

    await client.send_json_auto_id({"type": "config/label_registry/list"})

    msg = await client.receive_json()

    assert len(msg["result"]) == len(label_registry.labels)
    assert msg["result"][0] == {
        "color": None,
        "created_at": created_1.timestamp(),
        "description": None,
        "icon": None,
        "label_id": "mock_1",
        "modified_at": created_2.timestamp(),
        "name": "Mock 1...",
    }
    assert msg["result"][1] == {
        "color": "#00FF00",
        "created_at": created_2.timestamp(),
        "description": "This is the second label",
        "icon": "mdi:two",
        "label_id": "mock_2",
        "modified_at": created_2.timestamp(),
        "name": "mock 2",
    }


async def test_create_label(
    client: MockHAClientWebSocket,
    label_registry: lr.LabelRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test create entry."""
    created_1 = datetime.fromisoformat("2024-07-16T13:30:00.900075+00:00")
    freezer.move_to(created_1)
    await client.send_json_auto_id(
        {
            "name": "MOCK",
            "type": "config/label_registry/create",
        }
    )

    msg = await client.receive_json()

    assert len(label_registry.labels) == 1
    assert msg["result"] == {
        "color": None,
        "created_at": created_1.timestamp(),
        "description": None,
        "icon": None,
        "label_id": "mock",
        "name": "MOCK",
        "modified_at": created_1.timestamp(),
    }

    created_2 = datetime.fromisoformat("2024-07-17T13:30:00.900075+00:00")
    freezer.move_to(created_2)
    await client.send_json_auto_id(
        {
            "id": 2,
            "name": "MOCKERY",
            "type": "config/label_registry/create",
            "color": "#00FF00",
            "description": "This is the second label",
            "icon": "mdi:two",
        }
    )

    msg = await client.receive_json()

    assert len(label_registry.labels) == 2
    assert msg["result"] == {
        "color": "#00FF00",
        "created_at": created_2.timestamp(),
        "description": "This is the second label",
        "icon": "mdi:two",
        "label_id": "mockery",
        "modified_at": created_2.timestamp(),
        "name": "MOCKERY",
    }

    created_3 = datetime.fromisoformat("2024-07-18T13:30:00.900075+00:00")
    freezer.move_to(created_3)
    await client.send_json_auto_id(
        {
            "name": "MAGIC",
            "type": "config/label_registry/create",
            "color": "indigo",
            "description": "This is the third label",
            "icon": "mdi:three",
        }
    )

    msg = await client.receive_json()

    assert len(label_registry.labels) == 3
    assert msg["result"] == {
        "color": "indigo",
        "created_at": created_3.timestamp(),
        "description": "This is the third label",
        "icon": "mdi:three",
        "label_id": "magic",
        "modified_at": created_3.timestamp(),
        "name": "MAGIC",
    }


async def test_create_label_with_name_already_in_use(
    client: MockHAClientWebSocket,
    label_registry: lr.LabelRegistry,
) -> None:
    """Test create entry that should fail."""
    label_registry.async_create("mock")
    assert len(label_registry.labels) == 1

    await client.send_json_auto_id(
        {"name": "mock", "type": "config/label_registry/create"}
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_info"
    assert msg["error"]["message"] == "The name mock (mock) is already in use"
    assert len(label_registry.labels) == 1


async def test_delete_label(
    client: MockHAClientWebSocket,
    label_registry: lr.LabelRegistry,
) -> None:
    """Test delete entry."""
    label = label_registry.async_create("mock")
    assert len(label_registry.labels) == 1

    await client.send_json_auto_id(
        {"label_id": label.label_id, "type": "config/label_registry/delete"}
    )

    msg = await client.receive_json()

    assert msg["success"]
    assert not label_registry.labels


async def test_delete_non_existing_label(
    client: MockHAClientWebSocket,
    label_registry: lr.LabelRegistry,
) -> None:
    """Test delete entry that should fail."""
    label_registry.async_create("mock")
    assert len(label_registry.labels) == 1

    await client.send_json_auto_id(
        {"label_id": "omg_puppies", "type": "config/label_registry/delete"}
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_info"
    assert msg["error"]["message"] == "Label ID doesn't exist"
    assert len(label_registry.labels) == 1


async def test_update_label(
    client: MockHAClientWebSocket,
    label_registry: lr.LabelRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test update entry."""
    created_at = datetime.fromisoformat("2024-07-16T13:30:00.900075+00:00")
    freezer.move_to(created_at)
    label = label_registry.async_create("mock")
    assert len(label_registry.labels) == 1

    modified_at = datetime.fromisoformat("2024-07-16T13:45:00.900075+00:00")
    freezer.move_to(modified_at)

    await client.send_json_auto_id(
        {
            "label_id": label.label_id,
            "name": "UPDATED",
            "icon": "mdi:test",
            "color": "#00FF00",
            "description": "This is a label description",
            "type": "config/label_registry/update",
        }
    )

    msg = await client.receive_json()

    assert len(label_registry.labels) == 1
    assert msg["result"] == {
        "color": "#00FF00",
        "created_at": created_at.timestamp(),
        "description": "This is a label description",
        "icon": "mdi:test",
        "label_id": "mock",
        "modified_at": modified_at.timestamp(),
        "name": "UPDATED",
    }

    modified_at = datetime.fromisoformat("2024-07-16T13:50:00.900075+00:00")
    freezer.move_to(modified_at)

    await client.send_json_auto_id(
        {
            "label_id": label.label_id,
            "name": "UPDATED AGAIN",
            "icon": None,
            "color": None,
            "description": None,
            "type": "config/label_registry/update",
        }
    )

    msg = await client.receive_json()

    assert len(label_registry.labels) == 1
    assert msg["result"] == {
        "color": None,
        "created_at": created_at.timestamp(),
        "description": None,
        "icon": None,
        "label_id": "mock",
        "modified_at": modified_at.timestamp(),
        "name": "UPDATED AGAIN",
    }

    modified_at = datetime.fromisoformat("2024-07-16T13:55:00.900075+00:00")
    freezer.move_to(modified_at)

    await client.send_json_auto_id(
        {
            "label_id": label.label_id,
            "name": "UPDATED YET AGAIN",
            "icon": None,
            "color": "primary",
            "description": None,
            "type": "config/label_registry/update",
        }
    )

    msg = await client.receive_json()

    assert len(label_registry.labels) == 1
    assert msg["result"] == {
        "color": "primary",
        "created_at": created_at.timestamp(),
        "description": None,
        "icon": None,
        "label_id": "mock",
        "modified_at": modified_at.timestamp(),
        "name": "UPDATED YET AGAIN",
    }


async def test_update_with_name_already_in_use(
    client: MockHAClientWebSocket,
    label_registry: lr.LabelRegistry,
) -> None:
    """Test update entry."""
    label = label_registry.async_create("mock 1")
    label_registry.async_create("mock 2")
    assert len(label_registry.labels) == 2

    await client.send_json_auto_id(
        {
            "label_id": label.label_id,
            "name": "mock 2",
            "type": "config/label_registry/update",
        }
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_info"
    assert msg["error"]["message"] == "The name mock 2 (mock2) is already in use"
    assert len(label_registry.labels) == 2
