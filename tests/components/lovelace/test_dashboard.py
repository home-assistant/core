"""Test the Lovelace initialization."""

from collections.abc import Generator
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components import frontend
from homeassistant.components.lovelace import const, dashboard
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component, async_capture_events
from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True)
def mock_onboarding_done() -> Generator[MagicMock]:
    """Mock that Home Assistant is currently onboarding.

    Enabled to prevent creating default dashboards during test execution.
    """
    with patch(
        "homeassistant.components.onboarding.async_is_onboarded",
        return_value=True,
    ) as mock_onboarding:
        yield mock_onboarding


async def test_lovelace_from_storage_new_installation(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test new installation has default lovelace panel but no dashboard entry."""
    assert await async_setup_component(hass, "lovelace", {})

    # Default lovelace panel is registered for backward compatibility
    assert "lovelace" in hass.data[frontend.DATA_PANELS]

    client = await hass_ws_client(hass)

    # Dashboards list should be empty (no dashboard entry created)
    await client.send_json({"id": 5, "type": "lovelace/dashboards/list"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []


async def test_lovelace_from_storage_migration(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test we migrate existing lovelace config from storage to dashboard."""
    # Pre-populate storage with existing lovelace config
    hass_storage[dashboard.CONFIG_STORAGE_KEY_DEFAULT] = {
        "version": 1,
        "key": dashboard.CONFIG_STORAGE_KEY_DEFAULT,
        "data": {"config": {"views": [{"title": "Home"}]}},
    }

    assert await async_setup_component(hass, "lovelace", {})

    # After migration, lovelace panel should be registered as a dashboard
    assert "lovelace" in hass.data[frontend.DATA_PANELS]
    assert hass.data[frontend.DATA_PANELS]["lovelace"].config == {"mode": "storage"}

    client = await hass_ws_client(hass)

    # Dashboard should be in the list
    await client.send_json({"id": 5, "type": "lovelace/dashboards/list"})
    response = await client.receive_json()
    assert response["success"]
    assert len(response["result"]) == 1
    assert response["result"][0]["url_path"] == "lovelace"
    assert response["result"][0]["title"] == "Overview"

    # Fetch migrated config
    await client.send_json({"id": 6, "type": "lovelace/config", "url_path": "lovelace"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"views": [{"title": "Home"}]}

    # Old storage key should be gone, new one should exist
    assert dashboard.CONFIG_STORAGE_KEY_DEFAULT not in hass_storage
    assert dashboard.CONFIG_STORAGE_KEY.format("lovelace") in hass_storage

    # Store new config
    events = async_capture_events(hass, const.EVENT_LOVELACE_UPDATED)

    await client.send_json(
        {
            "id": 7,
            "type": "lovelace/config/save",
            "url_path": "lovelace",
            "config": {"yo": "hello"},
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert hass_storage[dashboard.CONFIG_STORAGE_KEY.format("lovelace")]["data"] == {
        "config": {"yo": "hello"}
    }
    assert len(events) == 1

    # Load new config
    await client.send_json({"id": 8, "type": "lovelace/config", "url_path": "lovelace"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"yo": "hello"}

    # Test with recovery mode
    hass.config.recovery_mode = True
    await client.send_json({"id": 9, "type": "lovelace/config", "url_path": "lovelace"})
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "config_not_found"

    await client.send_json(
        {
            "id": 10,
            "type": "lovelace/config/save",
            "url_path": "lovelace",
            "config": {"yo": "hello"},
        }
    )
    response = await client.receive_json()
    assert not response["success"]

    await client.send_json(
        {"id": 11, "type": "lovelace/config/delete", "url_path": "lovelace"}
    )
    response = await client.receive_json()
    assert not response["success"]


async def test_lovelace_dashboard_deleted_re_registers_panel(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test deleting the lovelace dashboard re-registers the default panel."""
    # Pre-populate storage with existing lovelace config (triggers migration)
    hass_storage[dashboard.CONFIG_STORAGE_KEY_DEFAULT] = {
        "version": 1,
        "key": dashboard.CONFIG_STORAGE_KEY_DEFAULT,
        "data": {"config": {"views": [{"title": "Home"}]}},
    }

    assert await async_setup_component(hass, "lovelace", {})

    # After migration, lovelace panel should be registered as a dashboard
    assert "lovelace" in hass.data[frontend.DATA_PANELS]

    client = await hass_ws_client(hass)

    # Dashboard should be in the list
    await client.send_json({"id": 5, "type": "lovelace/dashboards/list"})
    response = await client.receive_json()
    assert response["success"]
    assert len(response["result"]) == 1
    dashboard_id = response["result"][0]["id"]

    # Delete the lovelace dashboard
    await client.send_json(
        {"id": 6, "type": "lovelace/dashboards/delete", "dashboard_id": dashboard_id}
    )
    response = await client.receive_json()
    assert response["success"]

    # Dashboard should be gone from the list
    await client.send_json({"id": 7, "type": "lovelace/dashboards/list"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []

    # But the lovelace panel should still be registered (re-registered as default)
    assert "lovelace" in hass.data[frontend.DATA_PANELS]


async def test_lovelace_migration_completes_when_both_files_exist(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test migration completes when both old and new storage files exist."""
    # Pre-populate both old and new storage (simulating incomplete migration)
    hass_storage[dashboard.CONFIG_STORAGE_KEY_DEFAULT] = {
        "version": 1,
        "key": dashboard.CONFIG_STORAGE_KEY_DEFAULT,
        "data": {"config": {"views": [{"title": "Old"}]}},
    }
    hass_storage[dashboard.CONFIG_STORAGE_KEY.format("lovelace")] = {
        "version": 1,
        "key": dashboard.CONFIG_STORAGE_KEY.format("lovelace"),
        "data": {"config": {"views": [{"title": "New"}]}},
    }

    with patch("homeassistant.components.lovelace.os.rename") as mock_rename:
        assert await async_setup_component(hass, "lovelace", {})

    # Old file should be renamed as backup
    old_path = hass.config.path(".storage", dashboard.CONFIG_STORAGE_KEY_DEFAULT)
    mock_rename.assert_called_once_with(old_path, old_path + "_old")

    # Dashboard should be created, completing the incomplete migration
    client = await hass_ws_client(hass)
    await client.send_json({"id": 5, "type": "lovelace/dashboards/list"})
    response = await client.receive_json()
    assert response["success"]
    assert len(response["result"]) == 1
    assert response["result"][0]["url_path"] == "lovelace"

    # New storage data should be preserved (not overwritten with old data)
    await client.send_json({"id": 6, "type": "lovelace/config", "url_path": "lovelace"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"views": [{"title": "New"}]}


async def test_lovelace_migration_skipped_when_already_migrated(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test migration is skipped when dashboard already exists."""
    # Pre-populate dashboards with existing lovelace dashboard
    hass_storage[dashboard.DASHBOARDS_STORAGE_KEY] = {
        "version": 1,
        "key": dashboard.DASHBOARDS_STORAGE_KEY,
        "data": {
            "items": [
                {
                    "id": "lovelace",
                    "url_path": "lovelace",
                    "title": "Overview",
                    "icon": "mdi:view-dashboard",
                    "show_in_sidebar": True,
                    "require_admin": False,
                    "mode": "storage",
                }
            ]
        },
    }
    hass_storage[dashboard.CONFIG_STORAGE_KEY.format("lovelace")] = {
        "version": 1,
        "key": dashboard.CONFIG_STORAGE_KEY.format("lovelace"),
        "data": {"config": {"views": [{"title": "Home"}]}},
    }
    # Also have old file (should be ignored since dashboard exists)
    hass_storage[dashboard.CONFIG_STORAGE_KEY_DEFAULT] = {
        "version": 1,
        "key": dashboard.CONFIG_STORAGE_KEY_DEFAULT,
        "data": {"config": {"views": [{"title": "Old"}]}},
    }

    assert await async_setup_component(hass, "lovelace", {})

    client = await hass_ws_client(hass)
    await client.send_json({"id": 5, "type": "lovelace/dashboards/list"})
    response = await client.receive_json()
    assert response["success"]
    # Only the pre-existing dashboard, no duplicate
    assert len(response["result"]) == 1
    assert response["result"][0]["url_path"] == "lovelace"

    # Old storage should still exist (not touched)
    assert dashboard.CONFIG_STORAGE_KEY_DEFAULT in hass_storage


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

    # Make sure when the mtime changes, we reload the config
    with (
        patch(
            "homeassistant.components.lovelace.dashboard.load_yaml_dict",
            return_value={"hello": "yo3"},
        ),
        patch(
            "homeassistant.components.lovelace.dashboard.os.path.getmtime",
            return_value=time.time(),
        ),
    ):
        await client.send_json({"id": 9, "type": "lovelace/config", "force": False})
        response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"hello": "yo3"}

    assert len(events) == 2

    # If the mtime is lower, preserve the cache
    with (
        patch(
            "homeassistant.components.lovelace.dashboard.load_yaml_dict",
            return_value={"hello": "yo4"},
        ),
        patch(
            "homeassistant.components.lovelace.dashboard.os.path.getmtime",
            return_value=0,
        ),
    ):
        await client.send_json({"id": 10, "type": "lovelace/config", "force": False})
        response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"hello": "yo3"}

    assert len(events) == 2


async def test_lovelace_from_yaml_creates_repair_issue(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test YAML mode creates a repair issue."""
    assert await async_setup_component(hass, "lovelace", {"lovelace": {"mode": "YAML"}})

    # Panel should be registered as a YAML dashboard
    assert hass.data[frontend.DATA_PANELS]["lovelace"].config == {"mode": "yaml"}

    # Repair issue should be created
    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue("lovelace", "yaml_mode_deprecated")
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.WARNING
    assert issue.is_fixable is False
    assert issue.breaks_in_ha_version == "2026.8.0"


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
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test we load lovelace config from storage."""
    assert await async_setup_component(hass, "lovelace", {})

    # Default lovelace panel is registered for backward compatibility
    assert "lovelace" in hass.data[frontend.DATA_PANELS]

    client = await hass_ws_client(hass)

    # Fetch data
    await client.send_json({"id": 5, "type": "lovelace/dashboards/list"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []

    # Add a wrong dashboard (no hyphen)
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

    # Add a wrong dashboard (missing title)
    await client.send_json(
        {
            "id": 14,
            "type": "lovelace/dashboards/create",
            "url_path": "path",
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_format"

    # Add dashboard with existing url path
    await client.send_json(
        {
            "id": 15,
            "type": "lovelace/dashboards/create",
            "url_path": "created-url-path",
            "title": "Another title",
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "home_assistant_error"
    assert response["error"]["translation_key"] == "url_already_exists"
    assert response["error"]["translation_placeholders"]["url"] == "created-url-path"

    # Delete dashboards
    await client.send_json(
        {"id": 16, "type": "lovelace/dashboards/delete", "dashboard_id": dashboard_id}
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


async def test_lovelace_migration_sets_default_panel(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test migration sets default_panel to lovelace when not configured."""
    # Pre-populate storage with existing lovelace config
    hass_storage[dashboard.CONFIG_STORAGE_KEY_DEFAULT] = {
        "version": 1,
        "key": dashboard.CONFIG_STORAGE_KEY_DEFAULT,
        "data": {"config": {"views": [{"title": "Home"}]}},
    }

    # Need to setup frontend to register the websocket commands
    assert await async_setup_component(hass, "frontend", {})
    assert await async_setup_component(hass, "lovelace", {})

    # Verify default_panel was set in frontend system storage via websocket
    client = await hass_ws_client(hass)
    await client.send_json({"id": 5, "type": "frontend/get_system_data", "key": "core"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["value"]["default_panel"] == "lovelace"


async def test_lovelace_migration_preserves_existing_default_panel(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test migration does not override existing default_panel."""
    # Pre-populate storage with existing lovelace config
    hass_storage[dashboard.CONFIG_STORAGE_KEY_DEFAULT] = {
        "version": 1,
        "key": dashboard.CONFIG_STORAGE_KEY_DEFAULT,
        "data": {"config": {"views": [{"title": "Home"}]}},
    }
    # Pre-populate frontend system storage with existing default_panel
    storage_key = f"{frontend.DOMAIN}.system_data"
    hass_storage[storage_key] = {
        "version": 1,
        "key": storage_key,
        "data": {"core": {"default_panel": "other-dashboard"}},
    }

    # Need to setup frontend to register the websocket commands
    assert await async_setup_component(hass, "frontend", {})
    assert await async_setup_component(hass, "lovelace", {})

    # Verify default_panel was NOT overwritten via websocket
    client = await hass_ws_client(hass)
    await client.send_json({"id": 5, "type": "frontend/get_system_data", "key": "core"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["value"]["default_panel"] == "other-dashboard"


async def test_lovelace_no_migration_no_default_panel_set(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test no default_panel is set when there's nothing to migrate."""
    # Need to setup frontend to register the websocket commands
    assert await async_setup_component(hass, "frontend", {})
    # No pre-existing lovelace storage = no migration
    assert await async_setup_component(hass, "lovelace", {})

    # Verify default_panel was NOT set via websocket
    client = await hass_ws_client(hass)
    await client.send_json({"id": 5, "type": "frontend/get_system_data", "key": "core"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["value"] is None


async def test_lovelace_info_default(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test lovelace/info returns default resource_mode."""
    assert await async_setup_component(hass, "lovelace", {})

    client = await hass_ws_client(hass)

    await client.send_json({"id": 5, "type": "lovelace/info"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"resource_mode": "storage"}


async def test_lovelace_info_yaml_resource_mode(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test lovelace/info returns yaml resource_mode."""
    assert await async_setup_component(
        hass, "lovelace", {"lovelace": {"resource_mode": "yaml"}}
    )

    client = await hass_ws_client(hass)

    await client.send_json({"id": 5, "type": "lovelace/info"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"resource_mode": "yaml"}


async def test_lovelace_info_yaml_mode_fallback(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test lovelace/info returns yaml resource_mode when mode is yaml."""
    assert await async_setup_component(hass, "lovelace", {"lovelace": {"mode": "yaml"}})

    client = await hass_ws_client(hass)

    await client.send_json({"id": 5, "type": "lovelace/info"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"resource_mode": "yaml"}
