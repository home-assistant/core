"""Test the recorder settings configured from the UI."""

from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant.typing import WebSocketGenerator

from homeassistant.components.recorder import (
    CONF_COMMIT_INTERVAL,
    CONF_DB_URL,
    CONF_PURGE_KEEP_DAYS,
    DOMAIN,
    Recorder,
    get_instance,
)
from homeassistant.components.recorder.settings import DATA_SETTINGS_STORE
from homeassistant.const import CONF_EXCLUDE, CONF_INCLUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir, recorder as recorder_helper
from homeassistant.setup import async_setup_component

DEFAULT_SETTINGS = {
    "auto_purge": True,
    "auto_repack": True,
    "purge_keep_days": 10,
    "commit_interval": 5,
    "db_max_retries": 10,
    "db_retry_wait": 3,
    "include": {"domains": [], "entity_globs": [], "entities": []},
    "exclude": {"domains": [], "entity_globs": [], "entities": [], "event_types": []},
}


def _stored_settings(
    settings: dict[str, Any], *, yaml_migration_done: bool = True
) -> dict[str, Any]:
    """Return a recorder settings storage envelope."""
    return {
        "version": 1,
        "minor_version": 1,
        "key": DOMAIN,
        "data": {
            "settings": DEFAULT_SETTINGS | settings,
            "yaml_migration_done": yaml_migration_done,
        },
    }


async def _async_setup_recorder(
    hass: HomeAssistant, db_url: str, config: dict[str, Any]
) -> None:
    """Set up the recorder from YAML."""
    recorder_helper.async_initialize_recorder(hass)
    with patch("homeassistant.components.recorder.ALLOW_IN_MEMORY_DB", True):
        assert await async_setup_component(
            hass, DOMAIN, {DOMAIN: {CONF_DB_URL: db_url, **config}}
        )


async def test_yaml_migration(
    recorder_db_url: str,
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Test the YAML settings are imported once with a deprecation issue."""
    await _async_setup_recorder(
        hass,
        recorder_db_url,
        {
            "purge_keep_days": 30,
            "auto_repack": False,
            "include": {"domains": "light"},
            "exclude": {"entities": "light.excluded", "event_types": "my_event"},
        },
    )

    instance = get_instance(hass)
    assert instance.keep_days == 30
    assert instance.auto_repack is False
    assert instance.entity_filter is not None
    assert instance.entity_filter("light.kitchen")
    assert not instance.entity_filter("light.excluded")
    assert not instance.entity_filter("switch.kitchen")
    assert instance.exclude_event_types == {"my_event"}
    assert hass_storage[DOMAIN] == _stored_settings(
        {
            "purge_keep_days": 30,
            "auto_repack": False,
            "include": {"domains": ["light"], "entity_globs": [], "entities": []},
            "exclude": {
                "domains": [],
                "entity_globs": [],
                "entities": ["light.excluded"],
                "event_types": ["my_event"],
            },
        }
    )

    issue = issue_registry.async_get_issue(DOMAIN, "deprecated_yaml")
    assert issue is not None
    assert issue.breaks_in_ha_version == "2027.6.0"
    assert issue.translation_placeholders == {
        "options": "`auto_repack`, `exclude`, `include`, `purge_keep_days`"
    }


async def test_yaml_migration_drops_excluded_state_changed(
    recorder_db_url: str,
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test excluding state changed events in YAML is logged and not imported."""
    await _async_setup_recorder(
        hass,
        recorder_db_url,
        {"exclude": {"event_types": ["state_changed", "my_event"]}},
    )

    assert "State change events cannot be excluded" in caplog.text
    assert get_instance(hass).exclude_event_types == {"my_event"}
    assert hass_storage[DOMAIN]["data"]["settings"]["exclude"]["event_types"] == [
        "my_event"
    ]


async def test_no_yaml_settings_stores_nothing(
    recorder_db_url: str,
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Test nothing is stored and no issue is created without YAML settings."""
    await _async_setup_recorder(hass, recorder_db_url, {})

    assert get_instance(hass).keep_days == 10
    assert DOMAIN not in hass_storage
    assert not issue_registry.issues


async def test_yaml_ignored_after_migration(
    recorder_db_url: str,
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Test YAML settings are ignored with an issue once they were migrated."""
    hass_storage[DOMAIN] = _stored_settings({"purge_keep_days": 20})

    await _async_setup_recorder(hass, recorder_db_url, {"purge_keep_days": 30})

    assert get_instance(hass).keep_days == 20
    issue = issue_registry.async_get_issue(DOMAIN, "yaml_still_present_after_migration")
    assert issue is not None
    assert issue.translation_placeholders == {"options": "`purge_keep_days`"}
    assert issue_registry.async_get_issue(DOMAIN, "deprecated_yaml") is None


@pytest.mark.parametrize(
    "issue_id", ["deprecated_yaml", "yaml_still_present_after_migration"]
)
async def test_issues_cleared_when_yaml_removed(
    recorder_db_url: str,
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    hass_storage: dict[str, Any],
    issue_id: str,
) -> None:
    """Test the YAML issues are removed once the YAML settings are removed."""
    hass_storage[DOMAIN] = _stored_settings({})
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=issue_id,
        translation_placeholders={"options": "`purge_keep_days`"},
    )

    await _async_setup_recorder(hass, recorder_db_url, {})

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_stored_settings_merged_with_defaults(
    recorder_db_url: str,
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
) -> None:
    """Test settings missing from storage get their default value."""
    hass_storage[DOMAIN] = _stored_settings({})
    del hass_storage[DOMAIN]["data"]["settings"]["auto_purge"]

    await _async_setup_recorder(hass, recorder_db_url, {})

    assert get_instance(hass).auto_purge is True


@pytest.mark.usefixtures("recorder_mock")
async def test_ws_get_settings(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test getting the recorder settings."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "recorder/settings/get"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {
        # The test recorder commits every event
        "settings": DEFAULT_SETTINGS | {"commit_interval": 0},
        "default": DEFAULT_SETTINGS,
        "restart_required": False,
    }


async def test_ws_update_settings(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test settings are stored and applied to the running recorder."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "recorder/settings/update",
            "auto_purge": False,
            "auto_repack": False,
            "purge_keep_days": 30,
            "db_max_retries": 2,
            "db_retry_wait": 1,
        }
    )
    response = await client.receive_json()

    expected = DEFAULT_SETTINGS | {
        "auto_purge": False,
        "auto_repack": False,
        "purge_keep_days": 30,
        "commit_interval": 0,
        "db_max_retries": 2,
        "db_retry_wait": 1,
    }
    assert response["success"]
    assert response["result"] == {"settings": expected, "restart_required": False}
    assert recorder_mock.auto_purge is False
    assert recorder_mock.auto_repack is False
    assert recorder_mock.keep_days == 30
    assert recorder_mock.db_max_retries == 2
    assert recorder_mock.db_retry_wait == 1
    assert hass_storage[DOMAIN] == _stored_settings(expected)


@pytest.mark.parametrize(
    ("key", "value", "running_value"),
    [
        pytest.param(CONF_COMMIT_INTERVAL, 10, 0, id="commit_interval"),
        pytest.param(
            CONF_INCLUDE,
            {"domains": ["light"]},
            DEFAULT_SETTINGS["include"],
            id="include",
        ),
        pytest.param(
            CONF_EXCLUDE,
            {"event_types": ["my_event"]},
            DEFAULT_SETTINGS["exclude"],
            id="exclude",
        ),
    ],
)
async def test_ws_update_requires_restart(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    key: str,
    value: Any,
    running_value: Any,
) -> None:
    """Test settings read at start are stored and applied on the next restart."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "recorder/settings/update", key: value})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["restart_required"] is True
    assert recorder_mock.commit_interval == 0
    assert recorder_mock.entity_filter is None
    assert recorder_mock.exclude_event_types == set()

    await client.send_json_auto_id({"type": "recorder/settings/get"})
    response = await client.receive_json()
    assert response["result"]["restart_required"] is True

    # Changing it back to the running value means no restart is needed
    await client.send_json_auto_id(
        {"type": "recorder/settings/update", key: running_value}
    )
    response = await client.receive_json()
    assert response["result"]["restart_required"] is False


@pytest.mark.usefixtures("recorder_mock")
@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({CONF_PURGE_KEEP_DAYS: 0}, id="purge_keep_days"),
        pytest.param(
            {CONF_EXCLUDE: {"event_types": ["state_changed"]}}, id="state_changed"
        ),
    ],
)
async def test_ws_update_settings_invalid(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, changes: dict[str, Any]
) -> None:
    """Test invalid settings are rejected."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "recorder/settings/update", **changes})
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "invalid_format"
    assert hass.data[DATA_SETTINGS_STORE].settings == DEFAULT_SETTINGS | {
        "commit_interval": 0
    }


@pytest.mark.usefixtures("recorder_mock")
@pytest.mark.parametrize(
    "message",
    [
        {"type": "recorder/settings/get"},
        {"type": "recorder/settings/update", CONF_PURGE_KEEP_DAYS: 30},
    ],
)
async def test_ws_settings_require_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
    message: dict[str, Any],
) -> None:
    """Test the settings commands require an admin user."""
    client = await hass_ws_client(hass, hass_read_only_access_token)

    await client.send_json_auto_id(message)
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "unauthorized"
