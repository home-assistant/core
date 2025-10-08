"""Test Lovelace resources."""

import copy
from typing import Any
from unittest.mock import ANY, patch
import uuid

import pytest

from homeassistant.components.lovelace import dashboard, resources
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.typing import WebSocketGenerator

RESOURCE_EXAMPLES = [
    {"type": "js", "url": "/local/bla.js"},
    {"type": "css", "url": "/local/bla.css"},
]


@pytest.mark.parametrize("list_cmd", ["lovelace/resources", "lovelace/resources/list"])
async def test_yaml_resources(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, list_cmd: str
) -> None:
    """Test defining resources in configuration.yaml."""
    assert await async_setup_component(
        hass, "lovelace", {"lovelace": {"mode": "yaml", "resources": RESOURCE_EXAMPLES}}
    )

    client = await hass_ws_client(hass)

    # Fetch data
    await client.send_json({"id": 5, "type": list_cmd})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == RESOURCE_EXAMPLES


@pytest.mark.parametrize("list_cmd", ["lovelace/resources", "lovelace/resources/list"])
async def test_yaml_resources_backwards(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, list_cmd: str
) -> None:
    """Test defining resources in YAML ll config (legacy)."""
    with patch(
        "homeassistant.components.lovelace.dashboard.load_yaml_dict",
        return_value={"resources": RESOURCE_EXAMPLES},
    ):
        assert await async_setup_component(
            hass, "lovelace", {"lovelace": {"mode": "yaml"}}
        )

    client = await hass_ws_client(hass)

    # Fetch data
    await client.send_json({"id": 5, "type": list_cmd})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == RESOURCE_EXAMPLES


@pytest.mark.parametrize("list_cmd", ["lovelace/resources", "lovelace/resources/list"])
async def test_storage_resources(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    list_cmd: str,
) -> None:
    """Test defining resources in storage config."""
    resource_config = [{**item, "id": uuid.uuid4().hex} for item in RESOURCE_EXAMPLES]
    hass_storage[resources.RESOURCE_STORAGE_KEY] = {
        "key": resources.RESOURCE_STORAGE_KEY,
        "version": 1,
        "data": {"items": resource_config},
    }
    assert await async_setup_component(hass, "lovelace", {})

    client = await hass_ws_client(hass)

    # Fetch data
    await client.send_json({"id": 5, "type": list_cmd})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == resource_config


@pytest.mark.parametrize("list_cmd", ["lovelace/resources", "lovelace/resources/list"])
async def test_storage_resources_import(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    list_cmd: str,
) -> None:
    """Test importing resources from storage config."""
    assert await async_setup_component(hass, "lovelace", {})
    hass_storage[dashboard.CONFIG_STORAGE_KEY_DEFAULT] = {
        "key": "lovelace",
        "version": 1,
        "data": {"config": {"resources": copy.deepcopy(RESOURCE_EXAMPLES)}},
    }

    client = await hass_ws_client(hass)

    # Subscribe
    await client.send_json_auto_id({"type": "lovelace/resources/subscribe"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] is None
    event_id = response["id"]

    response = await client.receive_json()
    assert response["id"] == event_id
    assert response["event"] == []

    # Fetch data - this also loads the resources
    await client.send_json_auto_id({"type": list_cmd})

    response = await client.receive_json()
    assert response["id"] == event_id
    assert response["event"] == [
        {
            "change_type": "added",
            "item": {
                "id": ANY,
                "type": "js",
                "url": "/local/bla.js",
            },
            "resource_id": ANY,
        },
        {
            "change_type": "added",
            "item": {
                "id": ANY,
                "type": "css",
                "url": "/local/bla.css",
            },
            "resource_id": ANY,
        },
    ]

    response = await client.receive_json()
    assert response["success"]
    assert (
        response["result"]
        == hass_storage[resources.RESOURCE_STORAGE_KEY]["data"]["items"]
    )
    assert (
        "resources"
        not in hass_storage[dashboard.CONFIG_STORAGE_KEY_DEFAULT]["data"]["config"]
    )

    # Add a resource
    await client.send_json_auto_id(
        {
            "type": "lovelace/resources/create",
            "res_type": "module",
            "url": "/local/yo.js",
        }
    )
    response = await client.receive_json()
    assert response["id"] == event_id
    assert response["event"] == [
        {
            "change_type": "added",
            "item": {
                "id": ANY,
                "type": "module",
                "url": "/local/yo.js",
            },
            "resource_id": ANY,
        }
    ]

    response = await client.receive_json()
    assert response["success"]

    await client.send_json_auto_id({"type": list_cmd})
    response = await client.receive_json()
    assert response["success"]

    last_item = response["result"][-1]
    assert last_item["type"] == "module"
    assert last_item["url"] == "/local/yo.js"

    # Update a resource
    first_item = response["result"][0]

    await client.send_json_auto_id(
        {
            "type": "lovelace/resources/update",
            "resource_id": first_item["id"],
            "res_type": "css",
            "url": "/local/updated.css",
        }
    )
    response = await client.receive_json()
    assert response["id"] == event_id
    assert response["event"] == [
        {
            "change_type": "updated",
            "item": {
                "id": first_item["id"],
                "type": "css",
                "url": "/local/updated.css",
            },
            "resource_id": first_item["id"],
        }
    ]

    response = await client.receive_json()
    assert response["success"]

    await client.send_json_auto_id({"type": list_cmd})
    response = await client.receive_json()
    assert response["success"]

    first_item = response["result"][0]
    assert first_item["type"] == "css"
    assert first_item["url"] == "/local/updated.css"

    # Delete a resource
    await client.send_json_auto_id(
        {
            "type": "lovelace/resources/delete",
            "resource_id": first_item["id"],
        }
    )
    response = await client.receive_json()
    assert response["id"] == event_id
    assert response["event"] == [
        {
            "change_type": "removed",
            "item": {
                "id": first_item["id"],
                "type": "css",
                "url": "/local/updated.css",
            },
            "resource_id": first_item["id"],
        }
    ]

    response = await client.receive_json()
    assert response["success"]

    await client.send_json_auto_id({"type": list_cmd})
    response = await client.receive_json()
    assert response["success"]

    assert len(response["result"]) == 2
    assert first_item["id"] not in (item["id"] for item in response["result"])


@pytest.mark.parametrize("list_cmd", ["lovelace/resources", "lovelace/resources/list"])
async def test_storage_resources_import_invalid(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    list_cmd: str,
) -> None:
    """Test importing resources from storage config."""
    assert await async_setup_component(hass, "lovelace", {})
    hass_storage[dashboard.CONFIG_STORAGE_KEY_DEFAULT] = {
        "key": "lovelace",
        "version": 1,
        "data": {"config": {"resources": [{"invalid": "resource"}]}},
    }

    client = await hass_ws_client(hass)

    # Fetch data
    await client.send_json({"id": 5, "type": list_cmd})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []
    assert (
        "resources"
        in hass_storage[dashboard.CONFIG_STORAGE_KEY_DEFAULT]["data"]["config"]
    )


@pytest.mark.parametrize("list_cmd", ["lovelace/resources", "lovelace/resources/list"])
async def test_storage_resources_safe_mode(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    list_cmd: str,
) -> None:
    """Test defining resources in storage config."""

    resource_config = [{**item, "id": uuid.uuid4().hex} for item in RESOURCE_EXAMPLES]
    hass_storage[resources.RESOURCE_STORAGE_KEY] = {
        "key": resources.RESOURCE_STORAGE_KEY,
        "version": 1,
        "data": {"items": resource_config},
    }
    assert await async_setup_component(hass, "lovelace", {})

    client = await hass_ws_client(hass)
    hass.config.safe_mode = True

    # Fetch data
    await client.send_json({"id": 5, "type": list_cmd})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []
