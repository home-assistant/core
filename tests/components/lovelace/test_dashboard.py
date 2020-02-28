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

    await client.send_json(
        {"id": 9, "type": "lovelace/config/save", "config": {"yo": "hello"}}
    )
    response = await client.receive_json()
    assert not response["success"]

    await client.send_json({"id": 10, "type": "lovelace/config/delete"})
    response = await client.receive_json()
    assert not response["success"]


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
    assert dashboard.CONFIG_STORAGE_KEY_DEFAULT not in hass_storage

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
                        "require_admin": True,
                    },
                    "test-panel-no-sidebar": {"mode": "yaml", "filename": "bla2.yaml"},
                }
            }
        },
    )
    assert hass.data[frontend.DATA_PANELS]["test-panel"].config == {"mode": "yaml"}
    assert hass.data[frontend.DATA_PANELS]["test-panel-no-sidebar"].config == {
        "mode": "yaml"
    }

    client = await hass_ws_client(hass)

    # List dashboards
    await client.send_json({"id": 4, "type": "lovelace/dashboards/list"})
    response = await client.receive_json()
    assert response["success"]
    assert len(response["result"]) == 2
    with_sb, without_sb = response["result"]

    assert with_sb["mode"] == "yaml"
    assert with_sb["filename"] == "bla.yaml"
    assert with_sb["sidebar"] == {"title": "Test Panel", "icon": "mdi:test-icon"}
    assert with_sb["require_admin"] is True
    assert with_sb["url_path"] == "test-panel"

    assert without_sb["mode"] == "yaml"
    assert without_sb["filename"] == "bla2.yaml"
    assert "sidebar" not in without_sb
    assert without_sb["require_admin"] is False
    assert without_sb["url_path"] == "test-panel-no-sidebar"

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


async def test_storage_dashboards(hass, hass_ws_client, hass_storage):
    """Test we load lovelace config from storage."""
    assert await async_setup_component(hass, "lovelace", {})
    assert hass.data[frontend.DATA_PANELS]["lovelace"].config == {"mode": "storage"}

    client = await hass_ws_client(hass)

    # Fetch data
    await client.send_json({"id": 5, "type": "lovelace/dashboards/list"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []

    # Add a dashboard
    await client.send_json(
        {
            "id": 6,
            "type": "lovelace/dashboards/create",
            "url_path": "created_url_path",
            "require_admin": True,
            "sidebar": {"title": "Updated Title", "icon": "mdi:map"},
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["require_admin"] is True
    assert response["result"]["sidebar"] == {
        "title": "Updated Title",
        "icon": "mdi:map",
    }

    dashboard_id = response["result"]["id"]

    assert "created_url_path" in hass.data[frontend.DATA_PANELS]

    await client.send_json({"id": 7, "type": "lovelace/dashboards/list"})
    response = await client.receive_json()
    assert response["success"]
    assert len(response["result"]) == 1
    assert response["result"][0]["mode"] == "storage"
    assert response["result"][0]["sidebar"] == {
        "title": "Updated Title",
        "icon": "mdi:map",
    }
    assert response["result"][0]["require_admin"] is True

    # Fetch config
    await client.send_json(
        {"id": 8, "type": "lovelace/config", "url_path": "created_url_path"}
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "config_not_found"

    # Store new config
    events = async_capture_events(hass, const.EVENT_LOVELACE_UPDATED)

    await client.send_json(
        {
            "id": 9,
            "type": "lovelace/config/save",
            "url_path": "created_url_path",
            "config": {"yo": "hello"},
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert hass_storage[dashboard.CONFIG_STORAGE_KEY.format(dashboard_id)]["data"] == {
        "config": {"yo": "hello"}
    }
    assert len(events) == 1
    assert events[0].data["url_path"] == "created_url_path"

    await client.send_json(
        {"id": 10, "type": "lovelace/config", "url_path": "created_url_path"}
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"yo": "hello"}

    # Update a dashboard
    await client.send_json(
        {
            "id": 11,
            "type": "lovelace/dashboards/update",
            "dashboard_id": dashboard_id,
            "require_admin": False,
            "sidebar": None,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["require_admin"] is False
    assert "sidebar" not in response["result"]

    # Add dashboard with existing url path
    await client.send_json(
        {"id": 12, "type": "lovelace/dashboards/create", "url_path": "created_url_path"}
    )
    response = await client.receive_json()
    assert not response["success"]

    # Delete dashboards
    await client.send_json(
        {"id": 13, "type": "lovelace/dashboards/delete", "dashboard_id": dashboard_id}
    )
    response = await client.receive_json()
    assert response["success"]

    assert "created_url_path" not in hass.data[frontend.DATA_PANELS]
    assert dashboard.CONFIG_STORAGE_KEY.format(dashboard_id) not in hass_storage


async def test_websocket_list_dashboards(hass, hass_ws_client):
    """Test listing dashboards both storage + YAML."""
    assert await async_setup_component(
        hass,
        "lovelace",
        {
            "lovelace": {
                "dashboards": {
                    "test-panel-no-sidebar": {"mode": "yaml", "filename": "bla.yaml"},
                }
            }
        },
    )

    client = await hass_ws_client(hass)

    # Create a storage dashboard
    await client.send_json(
        {"id": 6, "type": "lovelace/dashboards/create", "url_path": "created_url_path"}
    )
    response = await client.receive_json()
    assert response["success"]

    # List dashboards
    await client.send_json({"id": 7, "type": "lovelace/dashboards/list"})
    response = await client.receive_json()
    assert response["success"]
    assert len(response["result"]) == 2
    with_sb, without_sb = response["result"]

    assert with_sb["mode"] == "yaml"
    assert with_sb["filename"] == "bla.yaml"
    assert with_sb["url_path"] == "test-panel-no-sidebar"

    assert without_sb["mode"] == "storage"
    assert without_sb["url_path"] == "created_url_path"
