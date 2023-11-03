"""Test label registry API."""
from collections.abc import Awaitable, Callable, Generator
from typing import Any

from aiohttp import ClientWebSocketResponse
import pytest

from homeassistant.components.config import label_registry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import label_registry as lr


@pytest.fixture(name="client")
def client_fixture(
    hass: HomeAssistant,
    hass_ws_client: Callable[
        [HomeAssistant], Awaitable[Generator[ClientWebSocketResponse, Any, Any]]
    ],
) -> Generator[ClientWebSocketResponse, None, None]:
    """Fixture that can interact with the config manager API."""
    hass.loop.run_until_complete(label_registry.async_setup(hass))
    return hass.loop.run_until_complete(hass_ws_client(hass))


async def test_list_labels(
    hass: HomeAssistant,
    client: ClientWebSocketResponse,
    label_registry: lr.LabelRegistry,
) -> None:
    """Test list entries."""
    label_registry.async_create("mock 1")
    label_registry.async_create(
        name="mock 2",
        color="#00FF00",
        icon="mdi:two",
        description="This is the second label",
    )

    assert len(label_registry.labels) == 2

    await client.send_json({"id": 1, "type": "config/label_registry/list"})

    msg = await client.receive_json()

    assert len(msg["result"]) == len(label_registry.labels)
    assert msg["result"][0] == {
        "color": None,
        "description": None,
        "icon": None,
        "label_id": "mock_1",
        "name": "mock 1",
    }
    assert msg["result"][1] == {
        "color": "#00FF00",
        "description": "This is the second label",
        "icon": "mdi:two",
        "label_id": "mock_2",
        "name": "mock 2",
    }


async def test_create_label(
    hass: HomeAssistant,
    client: ClientWebSocketResponse,
    label_registry: lr.LabelRegistry,
) -> None:
    """Test create entry."""
    await client.send_json(
        {
            "id": 1,
            "name": "MOCK",
            "type": "config/label_registry/create",
        }
    )

    msg = await client.receive_json()

    assert len(label_registry.labels) == 1
    assert msg["result"] == {
        "color": None,
        "description": None,
        "icon": None,
        "label_id": "mock",
        "name": "MOCK",
    }

    await client.send_json(
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
        "description": "This is the second label",
        "icon": "mdi:two",
        "label_id": "mockery",
        "name": "MOCKERY",
    }


async def test_create_label_with_name_already_in_use(
    hass: HomeAssistant,
    client: ClientWebSocketResponse,
    label_registry: lr.LabelRegistry,
) -> None:
    """Test create entry that should fail."""
    label_registry.async_create("mock")
    assert len(label_registry.labels) == 1

    await client.send_json(
        {"id": 1, "name": "mock", "type": "config/label_registry/create"}
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_info"
    assert msg["error"]["message"] == "The name mock (mock) is already in use"
    assert len(label_registry.labels) == 1


async def test_delete_label(
    hass: HomeAssistant,
    client: ClientWebSocketResponse,
    label_registry: lr.LabelRegistry,
) -> None:
    """Test delete entry."""
    label = label_registry.async_create("mock")
    assert len(label_registry.labels) == 1

    await client.send_json(
        {"id": 1, "label_id": label.label_id, "type": "config/label_registry/delete"}
    )

    msg = await client.receive_json()

    assert msg["success"]
    assert not label_registry.labels


async def test_delete_non_existing_label(
    hass: HomeAssistant,
    client: ClientWebSocketResponse,
    label_registry: lr.LabelRegistry,
) -> None:
    """Test delete entry that should fail."""
    label_registry.async_create("mock")
    assert len(label_registry.labels) == 1

    await client.send_json(
        {"id": 1, "label_id": "omg_puppies", "type": "config/label_registry/delete"}
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_info"
    assert msg["error"]["message"] == "Label ID doesn't exist"
    assert len(label_registry.labels) == 1


async def test_update_label(
    hass: HomeAssistant,
    client: ClientWebSocketResponse,
    label_registry: lr.LabelRegistry,
) -> None:
    """Test update entry."""
    label = label_registry.async_create("mock")
    assert len(label_registry.labels) == 1

    await client.send_json(
        {
            "id": 1,
            "label_id": label.label_id,
            "name": "UPDATED",
            "icon": "mdi:test",
            "color": "#00FF00",
            "description": "This is an label description",
            "type": "config/label_registry/update",
        }
    )

    msg = await client.receive_json()

    assert len(label_registry.labels) == 1
    assert msg["result"] == {
        "color": "#00FF00",
        "description": "This is an label description",
        "icon": "mdi:test",
        "label_id": "mock",
        "name": "UPDATED",
    }

    await client.send_json(
        {
            "id": 2,
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
        "description": None,
        "icon": None,
        "label_id": "mock",
        "name": "UPDATED AGAIN",
    }


async def test_update_with_name_already_in_use(
    hass: HomeAssistant,
    client: ClientWebSocketResponse,
    label_registry: lr.LabelRegistry,
) -> None:
    """Test update entry."""
    label = label_registry.async_create("mock 1")
    label_registry.async_create("mock 2")
    assert len(label_registry.labels) == 2

    await client.send_json(
        {
            "id": 1,
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
