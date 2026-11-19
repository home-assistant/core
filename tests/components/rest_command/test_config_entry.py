"""Tests for REST commands set up from a config entry."""

from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.rest_command.const import DOMAIN, SUBENTRY_TYPE_COMMAND
from homeassistant.config_entries import ConfigEntryState, ConfigSubentryData
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import TEST_URL


def _entry(*commands: dict[str, Any]) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="RESTful Command",
        subentries_data=[
            ConfigSubentryData(
                data=command,
                subentry_type=SUBENTRY_TYPE_COMMAND,
                title=command["action"],
                unique_id=command["action"],
            )
            for command in commands
        ],
    )


async def test_call_command_from_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a command from the UI renders its templates with the action data."""
    entry = _entry(
        {
            "action": "open_door",
            "url": TEST_URL + "{{ door }}",
            "method": "post",
            "payload": '{"door": "{{ door }}"}',
            "headers": {"X-Door": "{{ door }}"},
            "content_type": "application/json",
        }
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    aioclient_mock.post(
        TEST_URL + "front",
        content=b'{"ok": true}',
        headers={"Content-Type": "application/json"},
    )
    response = await hass.services.async_call(
        DOMAIN,
        "open_door",
        {"door": "front"},
        blocking=True,
        return_response=True,
    )

    assert response["content"] == {"ok": True}
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[0][2] == b'{"door": "front"}'
    assert aioclient_mock.mock_calls[0][3]["X-Door"] == "front"


async def test_unload_removes_actions(hass: HomeAssistant) -> None:
    """Test unloading the entry removes its actions only."""
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {"from_yaml": {"url": TEST_URL}}}
    )
    entry = _entry({"action": "from_ui", "url": TEST_URL})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.services.has_service(DOMAIN, "from_ui")

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.services.has_service(DOMAIN, "from_ui")
    assert hass.services.has_service(DOMAIN, "from_yaml")


async def test_yaml_reload_keeps_ui_actions(hass: HomeAssistant) -> None:
    """Test reloading YAML leaves the actions from the UI alone."""
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {"from_yaml": {"url": TEST_URL}}}
    )
    entry = _entry({"action": "from_ui", "url": TEST_URL})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={
            DOMAIN: {
                "new_yaml": {"url": TEST_URL},
                "from_ui": {"url": TEST_URL},
            }
        },
    ):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True)

    assert hass.services.has_service(DOMAIN, "from_ui")
    assert hass.services.has_service(DOMAIN, "new_yaml")
    assert not hass.services.has_service(DOMAIN, "from_yaml")

    # The UI action was not replaced by the YAML one with the same name
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert not hass.services.has_service(DOMAIN, "from_ui")


async def test_conflict_with_yaml(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a UI command with the name of a YAML command is not set up."""
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {"same": {"url": TEST_URL}}}
    )
    entry = _entry({"action": "same", "url": TEST_URL + "ui"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    subentry_id = next(iter(entry.subentries))
    issue = issue_registry.async_get_issue(DOMAIN, f"action_conflict_{subentry_id}")
    assert issue is not None
    assert issue.translation_placeholders == {"action": "rest_command.same"}

    # Unloading must not remove the action from YAML
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert hass.services.has_service(DOMAIN, "same")


async def test_conflict_issue_removed(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test the conflict issue goes away once the conflict is solved."""
    entry = _entry({"action": "same", "url": TEST_URL})
    entry.add_to_hass(hass)
    subentry_id = next(iter(entry.subentries))
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"action_conflict_{subentry_id}",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="action_conflict",
        translation_placeholders={"action": "rest_command.same"},
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, "same")
    assert (
        issue_registry.async_get_issue(DOMAIN, f"action_conflict_{subentry_id}") is None
    )


async def test_invalid_stored_command(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test a stored command that no longer validates is skipped."""
    entry = _entry(
        {"action": "broken", "url": "{{ door"},
        {"action": "working", "url": TEST_URL},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.services.has_service(DOMAIN, "broken")
    assert hass.services.has_service(DOMAIN, "working")
    assert "Invalid configuration for rest_command.broken" in caplog.text
