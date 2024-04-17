"""Test the Lovelace initialization."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components import frontend
from homeassistant.components.lovelace import const, dashboard
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component, async_capture_events
from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True)
def mock_onboarding_done() -> Generator[MagicMock, None, None]:
    """Mock that Home Assistant is currently onboarding.

    Enabled to prevent creating default dashboards during test execution.
    """
    with patch(
        "homeassistant.components.onboarding.async_is_onboarded",
        return_value=True,
    ) as mock_onboarding:
        yield mock_onboarding


async def test_lovelace_from_storage(
    hass: HomeAssistant, hass_ws_client, hass_storage: dict[str, Any]
) -> None:
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

    # Test with recovery mode
    hass.config.recovery_mode = True
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
    hass: HomeAssistant, hass_ws_client, hass_storage: dict[str, Any]
) -> None:
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


async def test_lovelace_from_storage_delete(
    hass: HomeAssistant, hass_ws_client, hass_storage: dict[str, Any]
) -> None:
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


async def test_lovelace_from_yaml(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
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
        "homeassistant.components.lovelace.dashboard.load_yaml_dict",
        return_value={"hello": "yo"},
    ):
        await client.send_json({"id": 7, "type": "lovelace/config"})
        response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"hello": "yo"}

    assert len(events) == 0

    # Fake new data to see we fire event
    with patch(
        "homeassistant.components.lovelace.dashboard.load_yaml_dict",
        return_value={"hello": "yo2"},
    ):
        await client.send_json({"id": 8, "type": "lovelace/config", "force": True})
        response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"hello": "yo2"}

    assert len(events) == 1


@pytest.mark.parametrize("url_path", ["test-panel", "test-panel-no-sidebar"])
async def test_dashboard_from_yaml(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, url_path
) -> None:
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
                        "title": "Test Panel",
                        "icon": "mdi:test-icon",
                        "show_in_sidebar": False,
                        "require_admin": True,
                    },
                    "test-panel-no-sidebar": {
                        "title": "Title No Sidebar",
                        "mode": "yaml",
                        "filename": "bla2.yaml",
                    },
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
    assert with_sb["title"] == "Test Panel"
    assert with_sb["icon"] == "mdi:test-icon"
    assert with_sb["show_in_sidebar"] is False
    assert with_sb["require_admin"] is True
    assert with_sb["url_path"] == "test-panel"

    assert without_sb["mode"] == "yaml"
    assert without_sb["filename"] == "bla2.yaml"
    assert without_sb["show_in_sidebar"] is True
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
        "homeassistant.components.lovelace.dashboard.load_yaml_dict",
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
        "homeassistant.components.lovelace.dashboard.load_yaml_dict",
        return_value={"hello": "yo2"},
    ):
        await client.send_json(
            {"id": 8, "type": "lovelace/config", "force": True, "url_path": url_path}
        )
        response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"hello": "yo2"}

    assert len(events) == 1


async def test_wrong_key_dashboard_from_yaml(hass: HomeAssistant) -> None:
    """Test we don't load lovelace dashboard without hyphen config from yaml."""
    with assert_setup_component(0, "lovelace"):
        assert not await async_setup_component(
            hass,
            "lovelace",
            {
                "lovelace": {
                    "dashboards": {
                        "testpanel": {
                            "mode": "yaml",
                            "filename": "bla.yaml",
                            "title": "Test Panel",
                            "icon": "mdi:test-icon",
                            "show_in_sidebar": False,
                            "require_admin": True,
                        }
                    }
                }
            },
        )


async def test_storage_dashboards(
    hass: HomeAssistant, hass_ws_client, hass_storage: dict[str, Any]
) -> None:
    """Test we load lovelace config from storage."""
    assert await async_setup_component(hass, "lovelace", {})
    assert hass.data[frontend.DATA_PANELS]["lovelace"].config == {"mode": "storage"}

    client = await hass_ws_client(hass)

    # Fetch data
    await client.send_json({"id": 5, "type": "lovelace/dashboards/list"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []

    # Add a wrong dashboard
    await client.send_json(
        {
            "id": 6,
            "type": "lovelace/dashboards/create",
            "url_path": "path",
            "title": "Test path without hyphen",
        }
    )
    response = await client.receive_json()
    assert not response["success"]

    # Add a dashboard
    await client.send_json(
        {
            "id": 7,
            "type": "lovelace/dashboards/create",
            "url_path": "created-url-path",
            "require_admin": True,
            "title": "New Title",
            "icon": "mdi:map",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["require_admin"] is True
    assert response["result"]["title"] == "New Title"
    assert response["result"]["icon"] == "mdi:map"

    dashboard_id = response["result"]["id"]

    assert "created-url-path" in hass.data[frontend.DATA_PANELS]

    await client.send_json({"id": 8, "type": "lovelace/dashboards/list"})
    response = await client.receive_json()
    assert response["success"]
    assert len(response["result"]) == 1
    assert response["result"][0]["mode"] == "storage"
    assert response["result"][0]["title"] == "New Title"
    assert response["result"][0]["icon"] == "mdi:map"
    assert response["result"][0]["show_in_sidebar"] is True
    assert response["result"][0]["require_admin"] is True

    # Fetch config
    await client.send_json(
        {"id": 9, "type": "lovelace/config", "url_path": "created-url-path"}
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "config_not_found"

    # Store new config
    events = async_capture_events(hass, const.EVENT_LOVELACE_UPDATED)

    await client.send_json(
        {
            "id": 10,
            "type": "lovelace/config/save",
            "url_path": "created-url-path",
            "config": {"yo": "hello"},
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert hass_storage[dashboard.CONFIG_STORAGE_KEY.format(dashboard_id)]["data"] == {
        "config": {"yo": "hello"}
    }
    assert len(events) == 1
    assert events[0].data["url_path"] == "created-url-path"

    await client.send_json(
        {"id": 11, "type": "lovelace/config", "url_path": "created-url-path"}
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"yo": "hello"}

    # Update a dashboard
    await client.send_json(
        {
            "id": 12,
            "type": "lovelace/dashboards/update",
            "dashboard_id": dashboard_id,
            "require_admin": False,
            "icon": "mdi:updated",
            "show_in_sidebar": False,
            "title": "Updated Title",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["mode"] == "storage"
    assert response["result"]["url_path"] == "created-url-path"
    assert response["result"]["title"] == "Updated Title"
    assert response["result"]["icon"] == "mdi:updated"
    assert response["result"]["show_in_sidebar"] is False
    assert response["result"]["require_admin"] is False

    # List dashboards again and make sure we see latest config
    await client.send_json({"id": 13, "type": "lovelace/dashboards/list"})
    response = await client.receive_json()
    assert response["success"]
    assert len(response["result"]) == 1
    assert response["result"][0]["mode"] == "storage"
    assert response["result"][0]["url_path"] == "created-url-path"
    assert response["result"][0]["title"] == "Updated Title"
    assert response["result"][0]["icon"] == "mdi:updated"
    assert response["result"][0]["show_in_sidebar"] is False
    assert response["result"][0]["require_admin"] is False

    # Add dashboard with existing url path
    await client.send_json(
        {"id": 14, "type": "lovelace/dashboards/create", "url_path": "created-url-path"}
    )
    response = await client.receive_json()
    assert not response["success"]

    # Delete dashboards
    await client.send_json(
        {"id": 15, "type": "lovelace/dashboards/delete", "dashboard_id": dashboard_id}
    )
    response = await client.receive_json()
    assert response["success"]

    assert "created-url-path" not in hass.data[frontend.DATA_PANELS]
    assert dashboard.CONFIG_STORAGE_KEY.format(dashboard_id) not in hass_storage


async def test_websocket_list_dashboards(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test listing dashboards both storage + YAML."""
    assert await async_setup_component(
        hass,
        "lovelace",
        {
            "lovelace": {
                "dashboards": {
                    "test-panel-no-sidebar": {
                        "title": "Test YAML",
                        "mode": "yaml",
                        "filename": "bla.yaml",
                    },
                }
            }
        },
    )

    client = await hass_ws_client(hass)

    # Create a storage dashboard
    await client.send_json(
        {
            "id": 6,
            "type": "lovelace/dashboards/create",
            "url_path": "created-url-path",
            "title": "Test Storage",
        }
    )
    response = await client.receive_json()
    assert response["success"]

    # List dashboards
    await client.send_json({"id": 8, "type": "lovelace/dashboards/list"})
    response = await client.receive_json()
    assert response["success"]
    assert len(response["result"]) == 2
    with_sb, without_sb = response["result"]

    assert with_sb["mode"] == "yaml"
    assert with_sb["title"] == "Test YAML"
    assert with_sb["filename"] == "bla.yaml"
    assert with_sb["url_path"] == "test-panel-no-sidebar"

    assert without_sb["mode"] == "storage"
    assert without_sb["title"] == "Test Storage"
    assert without_sb["url_path"] == "created-url-path"
