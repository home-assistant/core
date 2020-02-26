"""Test the Lovelace initialization."""
from unittest.mock import patch

import pytest

from homeassistant.components import frontend
from homeassistant.components.lovelace import const, dashboard
from homeassistant.setup import async_setup_component

from tests.common import async_capture_events, get_system_health_info


async def test_lovelace_from_storage(hass, hass_ws_client, hass_storage):
    """Test we load lovelace config from storage."""
    assert await async_setup_component(hass, "lovelace", {})
    assert hass.data[frontend.DATA_PANELS]["lovelace"].config == {"mode": "storage"}

    client = await hass_ws_client(hass)

    # Fetch data
    await client.send_json({"id": 5, "type": "lovelace/config"})
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "config_not_found"

    # Store new config
    events = async_capture_events(hass, const.EVENT_LOVELACE_UPDATED)

    await client.send_json(
        {"id": 6, "type": "lovelace/config/save", "config": {"yo": "hello"}}
    )
    response = await client.receive_json()
    assert response["success"]
    assert hass_storage[dashboard.CONFIG_STORAGE_KEY_DEFAULT]["data"] == {
        "config": {"yo": "hello"}
    }
    assert len(events) == 1

    # Load new config
    await client.send_json({"id": 7, "type": "lovelace/config"})
    response = await client.receive_json()
    assert response["success"]

    assert response["result"] == {"yo": "hello"}

    # Test with safe mode
    hass.config.safe_mode = True
    await client.send_json({"id": 8, "type": "lovelace/config"})
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "config_not_found"


async def test_lovelace_from_storage_save_before_load(
    hass, hass_ws_client, hass_storage
):
    """Test we can load lovelace config from storage."""
    assert await async_setup_component(hass, "lovelace", {})
    client = await hass_ws_client(hass)

    # Store new config
    await client.send_json(
        {"id": 6, "type": "lovelace/config/save", "config": {"yo": "hello"}}
    )
    response = await client.receive_json()
    assert response["success"]
    assert hass_storage[dashboard.CONFIG_STORAGE_KEY_DEFAULT]["data"] == {
        "config": {"yo": "hello"}
    }


async def test_lovelace_from_storage_delete(hass, hass_ws_client, hass_storage):
    """Test we delete lovelace config from storage."""
    assert await async_setup_component(hass, "lovelace", {})
    client = await hass_ws_client(hass)

    # Store new config
    await client.send_json(
        {"id": 6, "type": "lovelace/config/save", "config": {"yo": "hello"}}
    )
    response = await client.receive_json()
    assert response["success"]
    assert hass_storage[dashboard.CONFIG_STORAGE_KEY_DEFAULT]["data"] == {
        "config": {"yo": "hello"}
    }

    # Delete config
    await client.send_json({"id": 7, "type": "lovelace/config/delete"})
    response = await client.receive_json()
    assert response["success"]
    assert hass_storage[dashboard.CONFIG_STORAGE_KEY_DEFAULT]["data"] == {
        "config": None
    }

    # Fetch data
    await client.send_json({"id": 8, "type": "lovelace/config"})
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "config_not_found"


async def test_lovelace_from_yaml(hass, hass_ws_client):
    """Test we load lovelace config from yaml."""
    assert await async_setup_component(hass, "lovelace", {"lovelace": {"mode": "YAML"}})
    assert hass.data[frontend.DATA_PANELS]["lovelace"].config == {"mode": "yaml"}

    client = await hass_ws_client(hass)

    # Fetch data
    await client.send_json({"id": 5, "type": "lovelace/config"})
    response = await client.receive_json()
    assert not response["success"]

    assert response["error"]["code"] == "config_not_found"

    # Store new config not allowed
    await client.send_json(
        {"id": 6, "type": "lovelace/config/save", "config": {"yo": "hello"}}
    )
    response = await client.receive_json()
    assert not response["success"]

    # Patch data
    events = async_capture_events(hass, const.EVENT_LOVELACE_UPDATED)

    with patch(
        "homeassistant.components.lovelace.dashboard.load_yaml",
        return_value={"hello": "yo"},
    ):
        await client.send_json({"id": 7, "type": "lovelace/config"})
        response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"hello": "yo"}

    assert len(events) == 0

    # Fake new data to see we fire event
    with patch(
        "homeassistant.components.lovelace.dashboard.load_yaml",
        return_value={"hello": "yo2"},
    ):
        await client.send_json({"id": 8, "type": "lovelace/config", "force": True})
        response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"hello": "yo2"}

    assert len(events) == 1


async def test_system_health_info_autogen(hass):
    """Test system health info endpoint."""
    assert await async_setup_component(hass, "lovelace", {})
    info = await get_system_health_info(hass, "lovelace")
    assert info == {"mode": "auto-gen"}


async def test_system_health_info_storage(hass, hass_storage):
    """Test system health info endpoint."""
    hass_storage[dashboard.CONFIG_STORAGE_KEY_DEFAULT] = {
        "key": "lovelace",
        "version": 1,
        "data": {"config": {"resources": [], "views": []}},
    }
    assert await async_setup_component(hass, "lovelace", {})
    info = await get_system_health_info(hass, "lovelace")
    assert info == {"mode": "storage", "resources": 0, "views": 0}


async def test_system_health_info_yaml(hass):
    """Test system health info endpoint."""
    assert await async_setup_component(hass, "lovelace", {"lovelace": {"mode": "YAML"}})
    with patch(
        "homeassistant.components.lovelace.dashboard.load_yaml",
        return_value={"views": [{"cards": []}]},
    ):
        info = await get_system_health_info(hass, "lovelace")
    assert info == {"mode": "yaml", "resources": 0, "views": 1}


async def test_system_health_info_yaml_not_found(hass):
    """Test system health info endpoint."""
    assert await async_setup_component(hass, "lovelace", {"lovelace": {"mode": "YAML"}})
    info = await get_system_health_info(hass, "lovelace")
    assert info == {
        "mode": "yaml",
        "error": "{} not found".format(hass.config.path("ui-lovelace.yaml")),
    }


@pytest.mark.parametrize("url_path", ("test-panel", "test-panel-no-sidebar"))
async def test_dashboard_from_yaml(hass, hass_ws_client, url_path):
    """Test we load lovelace dashboard config from yaml."""
    assert await async_setup_component(
        hass,
        "lovelace",
        {
            "lovelace": {
                "dashboards": {
                    "test-panel": {
                        "mode": "yaml",
                        "filename": "bla.yaml",
                        "sidebar": {"title": "Test Panel", "icon": "mdi:test-icon"},
                    },
                    "test-panel-no-sidebar": {"mode": "yaml", "filename": "bla.yaml"},
                }
            }
        },
    )
    assert hass.data[frontend.DATA_PANELS]["test-panel"].config == {"mode": "yaml"}
    assert hass.data[frontend.DATA_PANELS]["test-panel-no-sidebar"].config == {
        "mode": "yaml"
    }

    client = await hass_ws_client(hass)

    # Fetch data
    await client.send_json({"id": 5, "type": "lovelace/config", "url_path": url_path})
    response = await client.receive_json()
    assert not response["success"]

    assert response["error"]["code"] == "config_not_found"

    # Store new config not allowed
    await client.send_json(
        {
            "id": 6,
            "type": "lovelace/config/save",
            "config": {"yo": "hello"},
            "url_path": url_path,
        }
    )
    response = await client.receive_json()
    assert not response["success"]

    # Patch data
    events = async_capture_events(hass, const.EVENT_LOVELACE_UPDATED)

    with patch(
        "homeassistant.components.lovelace.dashboard.load_yaml",
        return_value={"hello": "yo"},
    ):
        await client.send_json(
            {"id": 7, "type": "lovelace/config", "url_path": url_path}
        )
        response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"hello": "yo"}

    assert len(events) == 0

    # Fake new data to see we fire event
    with patch(
        "homeassistant.components.lovelace.dashboard.load_yaml",
        return_value={"hello": "yo2"},
    ):
        await client.send_json(
            {"id": 8, "type": "lovelace/config", "force": True, "url_path": url_path}
        )
        response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"hello": "yo2"}

    assert len(events) == 1
