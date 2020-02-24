"""Test Lovelace resources."""
import copy
import uuid

from asynctest import patch

from homeassistant.components.lovelace import dashboard, resources
from homeassistant.setup import async_setup_component

RESOURCE_EXAMPLES = [
    {"type": "js", "url": "/local/bla.js"},
    {"type": "css", "url": "/local/bla.css"},
]


async def test_yaml_resources(hass, hass_ws_client):
    """Test defining resources in configuration.yaml."""
    assert await async_setup_component(
        hass, "lovelace", {"lovelace": {"mode": "yaml", "resources": RESOURCE_EXAMPLES}}
    )

    client = await hass_ws_client(hass)

    # Fetch data
    await client.send_json({"id": 5, "type": "lovelace/resources"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == RESOURCE_EXAMPLES


async def test_yaml_resources_backwards(hass, hass_ws_client):
    """Test defining resources in YAML ll config (legacy)."""
    with patch(
        "homeassistant.components.lovelace.dashboard.load_yaml",
        return_value={"resources": RESOURCE_EXAMPLES},
    ):
        assert await async_setup_component(
            hass, "lovelace", {"lovelace": {"mode": "yaml"}}
        )

    client = await hass_ws_client(hass)

    # Fetch data
    await client.send_json({"id": 5, "type": "lovelace/resources"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == RESOURCE_EXAMPLES


async def test_storage_resources(hass, hass_ws_client, hass_storage):
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
    await client.send_json({"id": 5, "type": "lovelace/resources"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == resource_config


async def test_storage_resources_import(hass, hass_ws_client, hass_storage):
    """Test importing resources from storage config."""
    assert await async_setup_component(hass, "lovelace", {})
    hass_storage[dashboard.CONFIG_STORAGE_KEY_DEFAULT] = {
        "key": "lovelace",
        "version": 1,
        "data": {"config": {"resources": copy.deepcopy(RESOURCE_EXAMPLES)}},
    }

    client = await hass_ws_client(hass)

    # Fetch data
    await client.send_json({"id": 5, "type": "lovelace/resources"})
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


async def test_storage_resources_import_invalid(hass, hass_ws_client, hass_storage):
    """Test importing resources from storage config."""
    assert await async_setup_component(hass, "lovelace", {})
    hass_storage[dashboard.CONFIG_STORAGE_KEY_DEFAULT] = {
        "key": "lovelace",
        "version": 1,
        "data": {"config": {"resources": [{"invalid": "resource"}]}},
    }

    client = await hass_ws_client(hass)

    # Fetch data
    await client.send_json({"id": 5, "type": "lovelace/resources"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []
    assert (
        "resources"
        in hass_storage[dashboard.CONFIG_STORAGE_KEY_DEFAULT]["data"]["config"]
    )
