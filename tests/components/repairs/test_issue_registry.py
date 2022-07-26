"""Test the repairs websocket API."""
from typing import Any

import pytest

from homeassistant.components.repairs import async_create_issue, issue_registry
from homeassistant.components.repairs.const import DOMAIN
from homeassistant.components.repairs.issue_handler import (
    async_delete_issue,
    async_ignore_issue,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.setup import async_setup_component

from tests.common import flush_store


@pytest.fixture
def update_events(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Capture update events."""
    events: list[dict[str, Any]] = []

    @callback
    def async_capture(event):
        events.append(event.data)

    hass.bus.async_listen(
        issue_registry.EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED, async_capture
    )

    return events


async def test_load_issues(
    hass: HomeAssistant, update_events: list[dict[str, Any]]
) -> None:
    """Make sure that we can load/save data correctly."""
    assert await async_setup_component(hass, DOMAIN, {})

    issues = [
        {
            "breaks_in_ha_version": "2022.9",
            "domain": "test",
            "issue_id": "issue_1",
            "is_fixable": True,
            "learn_more_url": "https://theuselessweb.com",
            "severity": "error",
            "translation_key": "abc_123",
            "translation_placeholders": {"abc": "123"},
        },
        {
            "breaks_in_ha_version": "2022.8",
            "domain": "test",
            "issue_id": "issue_2",
            "is_fixable": True,
            "learn_more_url": "https://theuselessweb.com/abc",
            "severity": "other",
            "translation_key": "even_worse",
            "translation_placeholders": {"def": "456"},
        },
        {
            "breaks_in_ha_version": "2022.7",
            "domain": "test",
            "issue_id": "issue_3",
            "is_fixable": True,
            "learn_more_url": "https://checkboxrace.com",
            "severity": "other",
            "translation_key": "even_worse",
            "translation_placeholders": {"def": "789"},
        },
    ]

    for issue in issues:
        async_create_issue(
            hass,
            issue["domain"],
            issue["issue_id"],
            breaks_in_ha_version=issue["breaks_in_ha_version"],
            is_fixable=issue["is_fixable"],
            learn_more_url=issue["learn_more_url"],
            severity=issue["severity"],
            translation_key=issue["translation_key"],
            translation_placeholders=issue["translation_placeholders"],
        )

    await hass.async_block_till_done()

    assert len(update_events) == 3
    assert update_events[0]["action"] == "create"
    assert update_events[0]["domain"] == "test"
    assert update_events[0]["issue_id"] == "issue_1"
    assert update_events[1]["action"] == "create"
    assert update_events[1]["domain"] == "test"
    assert update_events[1]["issue_id"] == "issue_2"
    assert update_events[2]["action"] == "create"
    assert update_events[2]["domain"] == "test"
    assert update_events[2]["issue_id"] == "issue_3"

    async_ignore_issue(hass, issues[0]["domain"], issues[0]["issue_id"], True)
    await hass.async_block_till_done()

    assert len(update_events) == 4
    assert update_events[3]["action"] == "update"
    assert update_events[3]["domain"] == "test"
    assert update_events[3]["issue_id"] == "issue_1"

    async_delete_issue(hass, issues[2]["domain"], issues[2]["issue_id"])
    await hass.async_block_till_done()

    assert len(update_events) == 5
    assert update_events[4]["action"] == "remove"
    assert update_events[4]["domain"] == "test"
    assert update_events[4]["issue_id"] == "issue_3"

    registry: issue_registry.IssueRegistry = hass.data[issue_registry.DATA_REGISTRY]
    assert len(registry.issues) == 2
    issue1 = registry.async_get_issue("test", "issue_1")
    issue2 = registry.async_get_issue("test", "issue_2")

    registry2 = issue_registry.IssueRegistry(hass)
    await flush_store(registry._store)
    await registry2.async_load()

    assert list(registry.issues) == list(registry2.issues)

    issue1_registry2 = registry2.async_get_issue("test", "issue_1")
    assert issue1_registry2.created == issue1.created
    assert issue1_registry2.dismissed_version == issue1.dismissed_version
    issue2_registry2 = registry2.async_get_issue("test", "issue_2")
    assert issue2_registry2.created == issue2.created
    assert issue2_registry2.dismissed_version == issue2.dismissed_version


async def test_loading_issues_from_storage(hass: HomeAssistant, hass_storage) -> None:
    """Test loading stored issues on start."""
    hass_storage[issue_registry.STORAGE_KEY] = {
        "version": issue_registry.STORAGE_VERSION,
        "data": {
            "issues": [
                {
                    "created": "2022-07-19T09:41:13.746514+00:00",
                    "dismissed_version": "2022.7.0.dev0",
                    "domain": "test",
                    "issue_id": "issue_1",
                },
                {
                    "created": "2022-07-19T19:41:13.746514+00:00",
                    "dismissed_version": None,
                    "domain": "test",
                    "issue_id": "issue_2",
                },
            ]
        },
    }

    assert await async_setup_component(hass, DOMAIN, {})

    registry: issue_registry.IssueRegistry = hass.data[issue_registry.DATA_REGISTRY]
    assert len(registry.issues) == 2
