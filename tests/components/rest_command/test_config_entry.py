"""Tests for REST commands set up from a config entry."""

from typing import Any

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.rest_command.const import DOMAIN, SUBENTRY_TYPE_COMMAND
from homeassistant.config_entries import (
    SOURCE_IGNORE,
    SOURCE_IMPORT,
    ConfigEntryState,
    ConfigSubentryData,
)
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
    """Test unloading the entry removes its actions and keeps reload."""
    entry = _entry({"action": "from_ui", "url": TEST_URL})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.services.has_service(DOMAIN, "from_ui")

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.services.has_service(DOMAIN, "from_ui")
    assert hass.services.has_service(DOMAIN, "reload")


async def test_import_from_yaml(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the commands from YAML are imported into a new entry."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "open_door": {
                    "url": TEST_URL + "{{ door }}",
                    "method": "post",
                    "headers": {"X-Door": "{{ door }}"},
                    "username": "user",
                    "password": "secret",
                }
            }
        },
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.source == SOURCE_IMPORT
    assert entry.state is ConfigEntryState.LOADED
    subentry = next(iter(entry.subentries.values()))
    assert subentry.title == "open_door"
    assert subentry.unique_id == "open_door"
    assert subentry.data == {
        "action": "open_door",
        "url": TEST_URL + "{{ door }}",
        "method": "post",
        "headers": {"X-Door": "{{ door }}"},
        "username": "user",
        "password": "secret",
        "timeout": 10,
        "verify_ssl": True,
        "insecure_cipher": False,
        "skip_url_encoding": False,
    }
    assert issue_registry.async_get_issue(DOMAIN, "yaml_imported") is not None
    assert not hass.config_entries.subentries.async_progress()

    aioclient_mock.post(TEST_URL + "front")
    await hass.services.async_call(
        DOMAIN, "open_door", {"door": "front"}, blocking=True
    )
    assert aioclient_mock.mock_calls[0][3]["X-Door"] == "front"


async def test_import_only_new_commands(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test an import keeps the commands that were imported before."""
    entry = _entry({"action": "existing", "url": TEST_URL + "ui"})
    entry.add_to_hass(hass)

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "existing": {"url": TEST_URL + "yaml"},
                "new": {"url": TEST_URL},
            }
        },
    )
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    commands = {
        subentry.unique_id: subentry.data for subentry in entry.subentries.values()
    }
    assert commands["existing"]["url"] == TEST_URL + "ui"
    assert commands["new"]["url"] == TEST_URL
    assert hass.services.has_service(DOMAIN, "existing")
    assert hass.services.has_service(DOMAIN, "new")
    assert issue_registry.async_get_issue(DOMAIN, "yaml_imported") is not None


async def test_no_import_when_ignored(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test nothing is imported when the user ignored the integration."""
    MockConfigEntry(domain=DOMAIN, source=SOURCE_IGNORE).add_to_hass(hass)

    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {"from_yaml": {"url": TEST_URL}}}
    )
    await hass.async_block_till_done()

    assert not hass.services.has_service(DOMAIN, "from_yaml")
    assert issue_registry.async_get_issue(DOMAIN, "yaml_imported") is None


async def test_no_import_without_yaml(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test no entry is created when there is no YAML."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
    assert issue_registry.async_get_issue(DOMAIN, "yaml_imported") is None


async def test_invalid_stored_command(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test a stored command that no longer validates does not block the others."""
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
