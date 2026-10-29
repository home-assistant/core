"""Test the repairs websocket API."""

import asyncio
from collections.abc import Callable
import dataclasses
from functools import partial
import re
from typing import Any

import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_capture_events,
    flush_store,
)

from homeassistant.config_entries import ConfigEntryDisabler
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util


async def test_load_save_issues(hass: HomeAssistant) -> None:
    """Make sure that we can load/save data correctly."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    issues = [
        {
            "breaks_in_ha_version": "2022.9",
            "config_entry_id": entry.entry_id,
            "data": None,
            "domain": "test",
            "issue_domain": None,
            "issue_id": "issue_1",
            "is_fixable": True,
            "is_persistent": False,
            "learn_more_url": "https://theuselessweb.com",
            "severity": "error",
            "translation_key": "abc_123",
            "translation_placeholders": {"abc": "123"},
        },
        {
            "breaks_in_ha_version": "2022.8",
            "config_entry_id": None,
            "data": None,
            "domain": "test",
            "issue_domain": None,
            "issue_id": "issue_2",
            "is_fixable": True,
            "is_persistent": False,
            "learn_more_url": "https://theuselessweb.com/abc",
            "severity": "other",
            "translation_key": "even_worse",
            "translation_placeholders": {"def": "456"},
        },
        {
            "breaks_in_ha_version": "2022.7",
            "config_entry_id": None,
            "data": None,
            "domain": "test",
            "issue_domain": None,
            "issue_id": "issue_3",
            "is_fixable": True,
            "is_persistent": False,
            "learn_more_url": "https://checkboxrace.com",
            "severity": "other",
            "translation_key": "even_worse",
            "translation_placeholders": {"def": "789"},
        },
        {
            "breaks_in_ha_version": "2022.6",
            "config_entry_id": entry.entry_id,
            "data": {"entry_id": "123"},
            "domain": "test",
            "issue_domain": "blubb",
            "issue_id": "issue_4",
            "is_fixable": True,
            "is_persistent": True,
            "learn_more_url": "https://checkboxrace.com/blah",
            "severity": "other",
            "translation_key": "even_worse",
            "translation_placeholders": {"xyz": "abc"},
        },
        {
            "breaks_in_ha_version": None,
            "config_entry_id": None,
            "data": None,
            "domain": "test",
            "issue_domain": None,
            "issue_id": "issue_5",
            "is_fixable": False,
            "is_persistent": True,
            "learn_more_url": None,
            "severity": "warning",
            "translation_key": "bad",
            "translation_placeholders": None,
        },
    ]

    events = async_capture_events(hass, ir.EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED)

    for issue in issues:
        ir.async_create_issue(hass, **issue)

    await hass.async_block_till_done()

    assert [event.data for event in events] == [
        {"action": "create", "domain": "test", "issue_id": issue["issue_id"]}
        for issue in issues
    ]

    ir.async_ignore_issue(hass, issues[0]["domain"], issues[0]["issue_id"], True)
    await hass.async_block_till_done()

    assert len(events) == 6
    assert events[5].data == {
        "action": "update",
        "domain": "test",
        "issue_id": "issue_1",
    }

    ir.async_delete_issue(hass, issues[2]["domain"], issues[2]["issue_id"])
    await hass.async_block_till_done()

    assert len(events) == 7
    assert events[6].data == {
        "action": "remove",
        "domain": "test",
        "issue_id": "issue_3",
    }

    registry = hass.data[ir.DATA_REGISTRY]
    assert len(registry.issues) == 4

    registry2 = ir.IssueRegistry(hass)
    await flush_store(registry._store)
    await registry2.async_load()

    assert list(registry.issues) == list(registry2.issues)

    # Non-persistent issues are loaded as inactive skeletons
    for issue_id in ("issue_1", "issue_2"):
        issue = registry.async_get_issue("test", issue_id)
        assert registry2.async_get_issue("test", issue_id) == ir.IssueEntry(
            active=False,
            breaks_in_ha_version=None,
            config_entry_id=issue.config_entry_id,
            created=issue.created,
            data=None,
            dismissed_version=issue.dismissed_version,
            domain=issue.domain,
            is_fixable=None,
            is_persistent=False,
            issue_domain=None,
            issue_id=issue.issue_id,
            learn_more_url=None,
            severity=None,
            translation_key=None,
            translation_placeholders=None,
        )
    assert registry2.async_get_issue("test", "issue_1").config_entry_id == (
        entry.entry_id
    )
    assert registry2.async_get_issue("test", "issue_1").dismissed_version is not None
    for issue_id in ("issue_4", "issue_5"):
        assert registry2.async_get_issue("test", issue_id) == registry.async_get_issue(
            "test", issue_id
        )


UPDATED_ISSUE: dict[str, Any] = {
    "breaks_in_ha_version": "2023.1",
    "data": {"new": "data"},
    "is_fixable": True,
    "is_persistent": True,
    "issue_domain": "new_issue_domain",
    "learn_more_url": "https://www.example.com/something_changed",
    "severity": ir.IssueSeverity.WARNING,
    "translation_key": "new_key",
    "translation_placeholders": {"new": "placeholder"},
}


@pytest.mark.parametrize(
    "stored_issue",
    [
        pytest.param(
            {
                "config_entry_id": None,
                "created": "2022-07-19T09:41:13.746514+00:00",
                "dismissed_version": "2022.7.0.dev0",
                "domain": "test",
                "is_persistent": False,
                "issue_id": "issue_1",
            },
            id="inactive",
        ),
        pytest.param(
            {
                "breaks_in_ha_version": None,
                "config_entry_id": None,
                "created": "2022-07-19T09:41:13.746514+00:00",
                "data": None,
                "dismissed_version": "2022.7.0.dev0",
                "domain": "test",
                "is_fixable": False,
                "is_persistent": True,
                "issue_domain": None,
                "issue_id": "issue_1",
                "learn_more_url": None,
                "severity": "error",
                "translation_key": "abc_123",
                "translation_placeholders": None,
            },
            id="active",
        ),
    ],
)
@pytest.mark.parametrize("load_registries", [False])
async def test_update_issue_by_recreating(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    stored_issue: dict[str, Any],
) -> None:
    """Test re-creating an issue replaces its mutable fields."""
    hass_storage[ir.STORAGE_KEY] = {
        "version": ir.STORAGE_VERSION_MAJOR,
        "minor_version": ir.STORAGE_VERSION_MINOR,
        "data": {"issues": [stored_issue]},
    }
    await ir.async_load(hass)
    registry = ir.async_get(hass)
    old_issue = registry.async_get_issue("test", "issue_1")

    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    events = async_capture_events(hass, ir.EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED)

    ir.async_create_issue(
        hass, "test", "issue_1", config_entry_id=entry.entry_id, **UPDATED_ISSUE
    )
    await hass.async_block_till_done()

    assert registry.async_get_issue("test", "issue_1") == ir.IssueEntry(
        active=True,
        config_entry_id=entry.entry_id,
        created=old_issue.created,
        dismissed_version="2022.7.0.dev0",
        domain="test",
        issue_id="issue_1",
        **UPDATED_ISSUE,
    )
    assert [event.data for event in events] == [
        {"action": "update", "domain": "test", "issue_id": "issue_1"}
    ]

    # Nothing changed, no update event
    ir.async_create_issue(
        hass, "test", "issue_1", config_entry_id=entry.entry_id, **UPDATED_ISSUE
    )
    await hass.async_block_till_done()

    assert len(events) == 1


@pytest.mark.freeze_time("2022-07-21 08:22:00")
async def test_create_delete_issue_from_thread(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test the thread safe create_issue and delete_issue."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)

    await hass.async_add_executor_job(
        partial(
            ir.create_issue,
            hass,
            "test",
            "issue_1",
            config_entry_id=entry.entry_id,
            **UPDATED_ISSUE,
        )
    )

    assert issue_registry.async_get_issue("test", "issue_1") == ir.IssueEntry(
        active=True,
        config_entry_id=entry.entry_id,
        created=dt_util.utcnow(),
        dismissed_version=None,
        domain="test",
        issue_id="issue_1",
        **UPDATED_ISSUE,
    )

    await hass.async_add_executor_job(ir.delete_issue, hass, "test", "issue_1")

    assert issue_registry.async_get_issue("test", "issue_1") is None


@pytest.mark.parametrize("load_registries", [False])
async def test_load_save_issues_read_only(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Make sure that we don't save data when opened in read-only mode."""
    hass_storage[ir.STORAGE_KEY] = {
        "version": ir.STORAGE_VERSION_MAJOR,
        "minor_version": ir.STORAGE_VERSION_MINOR,
        "data": {
            "issues": [
                {
                    "config_entry_id": None,
                    "created": "2022-07-19T09:41:13.746514+00:00",
                    "dismissed_version": "2022.7.0.dev0",
                    "domain": "test",
                    "is_persistent": False,
                    "issue_id": "issue_1",
                },
            ]
        },
    }

    issues = [
        {
            "breaks_in_ha_version": "2022.8",
            "domain": "test",
            "issue_id": "issue_2",
            "is_fixable": True,
            "is_persistent": False,
            "learn_more_url": "https://theuselessweb.com/abc",
            "severity": "other",
            "translation_key": "even_worse",
            "translation_placeholders": {"def": "456"},
        },
    ]

    events = async_capture_events(hass, ir.EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED)
    await ir.async_load(hass, read_only=True)

    for issue in issues:
        ir.async_create_issue(
            hass,
            issue["domain"],
            issue["issue_id"],
            breaks_in_ha_version=issue["breaks_in_ha_version"],
            is_fixable=issue["is_fixable"],
            is_persistent=issue["is_persistent"],
            learn_more_url=issue["learn_more_url"],
            severity=issue["severity"],
            translation_key=issue["translation_key"],
            translation_placeholders=issue["translation_placeholders"],
        )

    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data == {
        "action": "create",
        "domain": "test",
        "issue_id": "issue_2",
    }

    registry = ir.async_get(hass)
    assert len(registry.issues) == 2

    registry2 = ir.IssueRegistry(hass)
    await flush_store(registry._store)
    await registry2.async_load()

    assert len(registry2.issues) == 1


@pytest.mark.parametrize("load_registries", [False])
async def test_loading_issues_from_storage(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test loading stored issues on start."""
    hass_storage[ir.STORAGE_KEY] = {
        "version": ir.STORAGE_VERSION_MAJOR,
        "minor_version": ir.STORAGE_VERSION_MINOR,
        "data": {
            "issues": [
                {
                    "config_entry_id": None,
                    "created": "2022-07-19T09:41:13.746514+00:00",
                    "dismissed_version": "2022.7.0.dev0",
                    "domain": "test",
                    "is_persistent": False,
                    "issue_id": "issue_1",
                },
                {
                    "config_entry_id": None,
                    "created": "2022-07-19T19:41:13.746514+00:00",
                    "dismissed_version": None,
                    "domain": "test",
                    "is_persistent": False,
                    "issue_id": "issue_2",
                },
                {
                    "breaks_in_ha_version": "2022.6",
                    "config_entry_id": None,
                    "created": "2022-07-19T19:41:13.746514+00:00",
                    "data": {"entry_id": "123"},
                    "dismissed_version": None,
                    "domain": "test",
                    "issue_domain": "blubb",
                    "issue_id": "issue_4",
                    "is_fixable": True,
                    "is_persistent": True,
                    "learn_more_url": "https://checkboxrace.com/blah",
                    "severity": "other",
                    "translation_key": "even_worse",
                    "translation_placeholders": {"xyz": "abc"},
                },
            ]
        },
    }

    await ir.async_load(hass)

    registry = hass.data[ir.DATA_REGISTRY]
    assert len(registry.issues) == 3


@pytest.mark.parametrize("load_registries", [False])
async def test_migration_1_1(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Test migration from version 1.1."""
    hass_storage[ir.STORAGE_KEY] = {
        "version": 1,
        "minor_version": 1,
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

    await ir.async_load(hass)

    registry = hass.data[ir.DATA_REGISTRY]
    assert len(registry.issues) == 2
    assert all(
        not issue.is_persistent and issue.config_entry_id is None
        for issue in registry.issues.values()
    )


@pytest.mark.parametrize("load_registries", [False])
async def test_migration_1_2(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Test migration from version 1.2."""
    hass_storage[ir.STORAGE_KEY] = {
        "version": 1,
        "minor_version": 2,
        "data": {
            "issues": [
                {
                    "created": "2022-07-19T09:41:13.746514+00:00",
                    "dismissed_version": "2022.7.0.dev0",
                    "domain": "test",
                    "is_persistent": False,
                    "issue_id": "issue_1",
                },
                {
                    "breaks_in_ha_version": "2022.6",
                    "created": "2022-07-19T19:41:13.746514+00:00",
                    "data": {"entry_id": "123"},
                    "dismissed_version": None,
                    "domain": "test",
                    "issue_domain": "blubb",
                    "issue_id": "issue_2",
                    "is_fixable": True,
                    "is_persistent": True,
                    "learn_more_url": "https://checkboxrace.com/blah",
                    "severity": "other",
                    "translation_key": "even_worse",
                    "translation_placeholders": {"xyz": "abc"},
                },
            ]
        },
    }

    await ir.async_load(hass)

    registry = hass.data[ir.DATA_REGISTRY]
    assert len(registry.issues) == 2
    assert registry.async_get_issue("test", "issue_1").config_entry_id is None
    assert registry.async_get_issue("test", "issue_2").config_entry_id is None

    registry.async_schedule_save()
    await flush_store(registry._store)
    assert hass_storage[ir.STORAGE_KEY]["minor_version"] == ir.STORAGE_VERSION_MINOR
    assert [
        issue["config_entry_id"]
        for issue in hass_storage[ir.STORAGE_KEY]["data"]["issues"]
    ] == [None, None]


async def test_create_issue_unknown_config_entry(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test linking an issue to an unknown config entry raises."""
    with pytest.raises(
        HomeAssistantError,
        match="Can't link issue to unknown config entry unknown_entry",
    ):
        ir.async_create_issue(
            hass,
            "test",
            "issue_1",
            config_entry_id="unknown_entry",
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="abc_123",
        )

    assert issue_registry.async_get_issue("test", "issue_1") is None


async def test_create_issue_config_entry_other_domain(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test an issue can be linked to a config entry of another domain."""
    entry = MockConfigEntry(domain="other")
    entry.add_to_hass(hass)

    ir.async_create_issue(
        hass,
        "test",
        "issue_1",
        config_entry_id=entry.entry_id,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="abc_123",
    )

    issue = issue_registry.async_get_issue("test", "issue_1")
    assert issue.config_entry_id == entry.entry_id


async def test_remove_config_entry_deletes_issues(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test removing a config entry deletes its issues and only its issues."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    other_entry = MockConfigEntry(domain="test")
    other_entry.add_to_hass(hass)

    for issue_id, config_entry_id in (
        ("active", entry.entry_id),
        ("inactive", entry.entry_id),
        ("other_entry", other_entry.entry_id),
        ("no_entry", None),
    ):
        ir.async_create_issue(
            hass,
            "other_domain",
            issue_id,
            config_entry_id=config_entry_id,
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="abc_123",
        )
    # Simulate an issue loaded from storage, which is inactive until re-created
    issue_registry.issues[("other_domain", "inactive")] = dataclasses.replace(
        issue_registry.issues[("other_domain", "inactive")], active=False
    )
    events = async_capture_events(hass, ir.EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED)

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert set(issue_registry.issues) == {
        ("other_domain", "other_entry"),
        ("other_domain", "no_entry"),
    }
    assert [event.data for event in events] == [
        {"action": "remove", "domain": "other_domain", "issue_id": "active"},
        {"action": "remove", "domain": "other_domain", "issue_id": "inactive"},
    ]


async def test_disable_config_entry_keeps_issues(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test disabling a config entry does not delete its issues."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    ir.async_create_issue(
        hass,
        "test",
        "issue_1",
        config_entry_id=entry.entry_id,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="abc_123",
    )

    await hass.config_entries.async_set_disabled_by(
        entry.entry_id, ConfigEntryDisabler.USER
    )
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue("test", "issue_1") is not None


@pytest.mark.parametrize("load_registries", [False])
async def test_load_removes_issues_of_unknown_config_entries(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test issues linked to config entries that no longer exist are removed."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)

    def _inactive(issue_id: str, config_entry_id: str | None) -> dict[str, Any]:
        return {
            "config_entry_id": config_entry_id,
            "created": "2022-07-19T09:41:13.746514+00:00",
            "dismissed_version": None,
            "domain": "test",
            "is_persistent": False,
            "issue_id": issue_id,
        }

    def _persistent(issue_id: str, config_entry_id: str | None) -> dict[str, Any]:
        return _inactive(issue_id, config_entry_id) | {
            "breaks_in_ha_version": None,
            "data": None,
            "is_fixable": False,
            "is_persistent": True,
            "issue_domain": None,
            "learn_more_url": None,
            "severity": "error",
            "translation_key": "abc_123",
            "translation_placeholders": None,
        }

    kept = [
        _inactive("inactive_known", entry.entry_id),
        _persistent("persistent_known", entry.entry_id),
        _inactive("inactive_no_entry", None),
        _persistent("persistent_no_entry", None),
    ]
    hass_storage[ir.STORAGE_KEY] = {
        "version": ir.STORAGE_VERSION_MAJOR,
        "minor_version": ir.STORAGE_VERSION_MINOR,
        "data": {
            "issues": [
                *kept,
                _inactive("inactive_unknown", "unknown_entry"),
                _persistent("persistent_unknown", "unknown_entry"),
            ]
        },
    }

    await ir.async_load(hass)
    registry = ir.async_get(hass)

    assert list(registry.issues) == [("test", issue["issue_id"]) for issue in kept]

    await flush_store(registry._store)
    assert hass_storage[ir.STORAGE_KEY]["data"]["issues"] == kept


@pytest.mark.parametrize("load_registries", [False])
async def test_load_waits_for_config_entries(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test load waits for config entries before removing unknown entries' issues.

    Config entries initialize concurrently with the issue registry, and may
    create issues while the issue registry waits for them.
    """
    present_entry = MockConfigEntry(domain="test")
    present_entry.add_to_hass(hass)
    late_entry = MockConfigEntry(domain="test")

    def _stored_issue(issue_id: str, config_entry_id: str) -> dict[str, Any]:
        return {
            "config_entry_id": config_entry_id,
            "created": "2022-07-19T09:41:13.746514+00:00",
            "dismissed_version": None,
            "domain": "test",
            "is_persistent": False,
            "issue_id": issue_id,
        }

    hass_storage[ir.STORAGE_KEY] = {
        "version": ir.STORAGE_VERSION_MAJOR,
        "minor_version": ir.STORAGE_VERSION_MINOR,
        "data": {
            "issues": [
                _stored_issue("late_entry", late_entry.entry_id),
                _stored_issue("unknown_entry", "unknown_entry"),
            ]
        },
    }
    # The hass fixture marks config entries as initialized
    hass.config_entries._initialized.clear()

    load_task = asyncio.create_task(ir.async_load(hass))
    await asyncio.sleep(0)
    assert not load_task.done()

    ir.async_create_issue(
        hass,
        "test",
        "created_while_waiting",
        config_entry_id=present_entry.entry_id,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="abc_123",
    )
    # The entry of a stored issue only becomes known when config entries
    # finish initializing
    late_entry.add_to_hass(hass)
    hass.config_entries._initialized.set()
    await load_task

    registry = ir.async_get(hass)
    assert list(registry.issues) == [
        ("test", "late_entry"),
        ("test", "created_while_waiting"),
    ]

    await flush_store(registry._store)
    assert [
        issue["issue_id"] for issue in hass_storage[ir.STORAGE_KEY]["data"]["issues"]
    ] == ["late_entry", "created_while_waiting"]


async def test_get_or_create_thread_safety(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test call async_get_or_create_from a thread."""
    with pytest.raises(
        RuntimeError,
        match=(
            "Detected code that calls issue_registry.async_get_or_create from a thread."
        ),
    ):
        await hass.async_add_executor_job(
            partial(
                ir.async_create_issue,
                hass,
                "any",
                "any",
                is_fixable=True,
                severity="error",
                translation_key="any",
            )
        )


async def test_async_delete_issue_thread_safety(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test call async_delete_issue from a thread."""
    ir.async_create_issue(
        hass,
        "any",
        "any",
        is_fixable=True,
        severity="error",
        translation_key="any",
    )

    with pytest.raises(
        RuntimeError,
        match="Detected code that calls issue_registry.async_delete from a thread.",
    ):
        await hass.async_add_executor_job(
            ir.async_delete_issue,
            hass,
            "any",
            "any",
        )


async def test_async_ignore_issue_thread_safety(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test call async_ignore_issue from a thread."""
    ir.async_create_issue(
        hass,
        "any",
        "any",
        is_fixable=True,
        severity="error",
        translation_key="any",
    )

    with pytest.raises(
        RuntimeError,
        match="Detected code that calls issue_registry.async_ignore from a thread.",
    ):
        await hass.async_add_executor_job(
            ir.async_ignore_issue, hass, "any", "any", True
        )


def _create_issue(
    hass: HomeAssistant,
    issue_id: str,
    domain: str = "test",
    config_entry_id: str | None = None,
) -> None:
    """Create an issue with fixed properties."""
    ir.async_create_issue(
        hass,
        domain,
        issue_id,
        config_entry_id=config_entry_id,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="abc",
    )


@pytest.mark.usefixtures("issue_registry")
async def test_refresh_issues(hass: HomeAssistant) -> None:
    """Test a refresh deletes only issues which were not created again."""
    for issue_id in ("refresh_1", "refresh_2", "refresh_3", "other"):
        _create_issue(hass, issue_id)
    _create_issue(hass, "refresh_4", domain="other_domain")
    ir.async_ignore_issue(hass, "test", "refresh_1", True)
    events = async_capture_events(hass, ir.EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED)

    refresh = ir.async_refresh_issues(hass, "test", issue_id_pattern="refresh_")
    _create_issue(hass, "refresh_1")
    _create_issue(hass, "refresh_5")
    refresh.async_keep(["refresh_2"])
    # Recreating unchanged issues and keeping issues fires no events
    await hass.async_block_till_done()
    assert [event.data for event in events] == [
        {"action": "create", "domain": "test", "issue_id": "refresh_5"}
    ]

    refresh.async_finish()
    await hass.async_block_till_done()

    assert [event.data for event in events[1:]] == [
        {"action": "remove", "domain": "test", "issue_id": "refresh_3"}
    ]
    issue_registry = ir.async_get(hass)
    assert set(issue_registry.issues) == {
        ("test", "refresh_1"),
        ("test", "refresh_2"),
        ("test", "refresh_5"),
        ("test", "other"),
        ("other_domain", "refresh_4"),
    }
    assert issue_registry.issues[("test", "refresh_1")].dismissed_version is not None


@pytest.mark.usefixtures("issue_registry")
async def test_refresh_issues_by_id(hass: HomeAssistant) -> None:
    """Test a refresh of explicit issue ids."""
    for issue_id in ("issue_1", "issue_2", "issue_3"):
        _create_issue(hass, issue_id)

    with ir.async_refresh_issues(
        hass, "test", issue_ids=["issue_1", "issue_2", "non_existing"]
    ):
        _create_issue(hass, "issue_1")

    assert set(ir.async_get(hass).issues) == {("test", "issue_1"), ("test", "issue_3")}


@pytest.mark.parametrize(
    ("issue_id_pattern", "expected_deleted"),
    [
        pytest.param("a_", {"a_1", "a_10"}, id="prefix"),
        pytest.param("(a|b)_", {"a_1", "a_10", "b_1"}, id="alternation"),
        # Matched from the start of the id, never inside it
        pytest.param("_1", set(), id="mid_id"),
        pytest.param("a_1", {"a_1", "a_10"}, id="not_anchored_at_end"),
        pytest.param("a_1$", {"a_1"}, id="end_anchor"),
        pytest.param(".*_1$", {"a_1", "b_1", "c_1", "x_a_1"}, id="leading_wildcard"),
        pytest.param(re.compile("(a|b)_"), {"a_1", "a_10", "b_1"}, id="compiled"),
    ],
)
@pytest.mark.usefixtures("issue_registry")
async def test_refresh_issues_pattern(
    hass: HomeAssistant,
    issue_id_pattern: str | re.Pattern[str],
    expected_deleted: set[str],
) -> None:
    """Test a refresh of issues matching a pattern from the start of the id."""
    issue_ids = {"a_1", "a_10", "b_1", "c_1", "x_a_1"}
    for issue_id in issue_ids:
        _create_issue(hass, issue_id)

    with ir.async_refresh_issues(hass, "test", issue_id_pattern=issue_id_pattern):
        pass

    assert set(ir.async_get(hass).issues) == {
        ("test", issue_id) for issue_id in issue_ids - expected_deleted
    }


@pytest.mark.usefixtures("issue_registry")
async def test_refresh_issues_context_manager_exception(hass: HomeAssistant) -> None:
    """Test a refresh is cancelled if an exception is raised."""
    _create_issue(hass, "refresh_1")

    with (
        pytest.raises(ValueError, match="Boom"),
        ir.async_refresh_issues(hass, "test", issue_id_pattern="refresh_"),
    ):
        raise ValueError("Boom")

    assert set(ir.async_get(hass).issues) == {("test", "refresh_1")}


@pytest.mark.usefixtures("issue_registry")
async def test_refresh_issues_cancel(hass: HomeAssistant) -> None:
    """Test a cancelled refresh does not delete issues, also if finished later."""
    _create_issue(hass, "refresh_1")

    refresh = ir.async_refresh_issues(hass, "test", issue_id_pattern="refresh_")
    refresh.async_cancel()
    refresh.async_finish()

    assert set(ir.async_get(hass).issues) == {("test", "refresh_1")}


@pytest.mark.usefixtures("issue_registry")
async def test_refresh_issues_finish_twice(hass: HomeAssistant) -> None:
    """Test finishing a refresh again does not delete issues created after it."""
    _create_issue(hass, "refresh_1")

    refresh = ir.async_refresh_issues(hass, "test", issue_id_pattern="refresh_")
    refresh.async_finish()
    _create_issue(hass, "refresh_1")
    refresh.async_finish()

    assert set(ir.async_get(hass).issues) == {("test", "refresh_1")}


@pytest.mark.usefixtures("issue_registry")
async def test_refresh_issues_deleted_during_refresh(hass: HomeAssistant) -> None:
    """Test an issue deleted and created again during a refresh is not deleted."""
    _create_issue(hass, "refresh_1")

    refresh = ir.async_refresh_issues(hass, "test", issue_id_pattern="refresh_")
    ir.async_delete_issue(hass, "test", "refresh_1")
    _create_issue(hass, "refresh_1")
    refresh.async_finish()

    assert set(ir.async_get(hass).issues) == {("test", "refresh_1")}


@pytest.mark.usefixtures("issue_registry")
async def test_refresh_issues_overlapping(hass: HomeAssistant) -> None:
    """Test a newer refresh takes over pending deletion from an older one."""
    _create_issue(hass, "refresh_1")
    _create_issue(hass, "refresh_2")

    refresh_old = ir.async_refresh_issues(hass, "test", issue_id_pattern="refresh_")
    refresh_new = ir.async_refresh_issues(hass, "test", issue_ids=["refresh_1"])
    refresh_old.async_finish()
    assert set(ir.async_get(hass).issues) == {("test", "refresh_1")}

    refresh_new.async_finish()
    assert ir.async_get(hass).issues == {}


@pytest.mark.parametrize("load_registries", [False])
async def test_refresh_issues_inactive(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test a refresh includes inactive issues loaded from storage."""
    hass_storage[ir.STORAGE_KEY] = {
        "version": ir.STORAGE_VERSION_MAJOR,
        "minor_version": ir.STORAGE_VERSION_MINOR,
        "data": {
            "issues": [
                {
                    "config_entry_id": None,
                    "created": "2022-07-19T09:41:13.746514+00:00",
                    "dismissed_version": "2022.7.0.dev0",
                    "domain": "test",
                    "is_persistent": False,
                    "issue_id": issue_id,
                }
                for issue_id in ("refresh_1", "refresh_2")
            ]
        },
    }
    await ir.async_load(hass)
    issue_registry = ir.async_get(hass)
    assert not issue_registry.issues[("test", "refresh_1")].active

    with ir.async_refresh_issues(hass, "test", issue_id_pattern="refresh_"):
        _create_issue(hass, "refresh_1")

    assert set(issue_registry.issues) == {("test", "refresh_1")}
    issue = issue_registry.issues[("test", "refresh_1")]
    assert issue.active
    assert issue.dismissed_version == "2022.7.0.dev0"


@pytest.mark.parametrize(
    "issue_id_pattern",
    [pytest.param("a", id="str"), pytest.param(re.compile("a"), id="compiled")],
)
@pytest.mark.usefixtures("issue_registry")
async def test_refresh_issues_invalid_scope(
    hass: HomeAssistant, issue_id_pattern: str | re.Pattern[str]
) -> None:
    """Test issue_id_pattern and issue_ids can't be combined."""
    with pytest.raises(
        ValueError, match="At most one of issue_id_pattern and issue_ids is allowed"
    ):
        ir.async_refresh_issues(
            hass, "test", issue_id_pattern=issue_id_pattern, issue_ids=[]
        )


@pytest.mark.usefixtures("issue_registry")
async def test_refresh_issues_domain(hass: HomeAssistant) -> None:
    """Test a refresh without pattern or ids covers all issues of the domain."""
    for issue_id in ("issue_1", "issue_2", "other_1"):
        _create_issue(hass, issue_id)
    _create_issue(hass, "issue_3", domain="other_domain")

    with ir.async_refresh_issues(hass, "test"):
        _create_issue(hass, "issue_1")

    assert set(ir.async_get(hass).issues) == {
        ("test", "issue_1"),
        ("other_domain", "issue_3"),
    }


@pytest.mark.parametrize(
    ("kwargs", "expected_deleted"),
    [
        pytest.param({}, {"a_1", "b_1", "a_inactive"}, id="entry"),
        pytest.param({"issue_id_pattern": "a_"}, {"a_1", "a_inactive"}, id="pattern"),
        pytest.param(
            {"issue_ids": ["a_1", "a_other", "a_none"]}, {"a_1"}, id="issue_ids"
        ),
    ],
)
@pytest.mark.parametrize("load_registries", [False])
async def test_refresh_issues_config_entry(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    kwargs: dict[str, Any],
    expected_deleted: set[str],
) -> None:
    """Test a refresh limited to the issues of a config entry."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    other_entry = MockConfigEntry(domain="test")
    other_entry.add_to_hass(hass)
    hass_storage[ir.STORAGE_KEY] = {
        "version": ir.STORAGE_VERSION_MAJOR,
        "minor_version": ir.STORAGE_VERSION_MINOR,
        "data": {
            "issues": [
                {
                    "config_entry_id": config_entry_id,
                    "created": "2022-07-19T09:41:13.746514+00:00",
                    "dismissed_version": "2022.7.0.dev0",
                    "domain": "test",
                    "is_persistent": False,
                    "issue_id": issue_id,
                }
                for issue_id, config_entry_id in (
                    ("a_inactive", entry.entry_id),
                    ("a_inactive_other", other_entry.entry_id),
                    ("a_inactive_none", None),
                )
            ]
        },
    }
    await ir.async_load(hass)
    for issue_id in ("a_1", "b_1", "a_kept"):
        _create_issue(hass, issue_id, config_entry_id=entry.entry_id)
    _create_issue(hass, "a_other", config_entry_id=other_entry.entry_id)
    _create_issue(hass, "a_none")
    _create_issue(hass, "a_other_domain", "other", config_entry_id=entry.entry_id)
    issues_before = set(ir.async_get(hass).issues)

    with ir.async_refresh_issues(
        hass, "test", config_entry_id=entry.entry_id, **kwargs
    ):
        _create_issue(hass, "a_kept", config_entry_id=entry.entry_id)

    assert set(ir.async_get(hass).issues) == issues_before - {
        ("test", issue_id) for issue_id in expected_deleted
    }


@pytest.mark.usefixtures("issue_registry")
async def test_delete_deferred_to_refresh(hass: HomeAssistant) -> None:
    """Test a deferred delete leaves the issue to the refresh which owns it."""
    _create_issue(hass, "issue_1")
    _create_issue(hass, "issue_2")
    issue_registry = ir.async_get(hass)

    refresh = ir.async_refresh_issues(hass, "test")
    ir.async_delete_issue(hass, "test", "issue_1", defer_to_refresh=True)
    issue_registry.async_delete("test", "issue_2", defer_to_refresh=True)
    assert set(issue_registry.issues) == {("test", "issue_1"), ("test", "issue_2")}

    _create_issue(hass, "issue_2")
    refresh.async_finish()
    assert set(issue_registry.issues) == {("test", "issue_2")}


@pytest.mark.usefixtures("issue_registry")
async def test_delete_deferred_without_refresh(hass: HomeAssistant) -> None:
    """Test a deferred delete deletes immediately if no refresh is in progress."""
    _create_issue(hass, "issue_1")

    ir.async_delete_issue(hass, "test", "issue_1", defer_to_refresh=True)

    assert ir.async_get(hass).issues == {}


@pytest.mark.usefixtures("issue_registry")
async def test_delete_deferred_outside_refresh_scope(hass: HomeAssistant) -> None:
    """Test a deferred delete deletes immediately if no refresh covers the issue."""
    _create_issue(hass, "issue_1")
    _create_issue(hass, "other")

    refresh = ir.async_refresh_issues(hass, "test", issue_ids=["other"])
    # Created after the refresh began, so not in its set
    _create_issue(hass, "issue_2")
    ir.async_delete_issue(hass, "test", "issue_1", defer_to_refresh=True)
    ir.async_delete_issue(hass, "test", "issue_2", defer_to_refresh=True)

    assert set(ir.async_get(hass).issues) == {("test", "other")}
    refresh.async_finish()


type _RefreshStep = Callable[[HomeAssistant, dict[str, ir.IssuesRefresh]], None]


def _recreate(hass: HomeAssistant, refreshes: dict[str, ir.IssuesRefresh]) -> None:
    _create_issue(hass, "issue_1")


def _defer_delete(hass: HomeAssistant, refreshes: dict[str, ir.IssuesRefresh]) -> None:
    ir.async_delete_issue(hass, "test", "issue_1", defer_to_refresh=True)


def _assert_present(
    hass: HomeAssistant, refreshes: dict[str, ir.IssuesRefresh]
) -> None:
    assert ("test", "issue_1") in ir.async_get(hass).issues


def _keep(name: str) -> _RefreshStep:
    return lambda hass, refreshes: refreshes[name].async_keep(["issue_1"])


def _keep_issue(hass: HomeAssistant, refreshes: dict[str, ir.IssuesRefresh]) -> None:
    ir.async_keep_issue(hass, "test", "issue_1")


def _finish(name: str) -> _RefreshStep:
    return lambda hass, refreshes: refreshes[name].async_finish()


def _cancel(name: str) -> _RefreshStep:
    return lambda hass, refreshes: refreshes[name].async_cancel()


@pytest.mark.parametrize(
    ("refresh_names", "steps", "kept"),
    [
        pytest.param(
            ["new"],
            [_recreate, _defer_delete, _finish("new")],
            True,
            id="recreate_defer_finish",
        ),
        pytest.param(
            ["new"],
            [_defer_delete, _recreate, _finish("new")],
            True,
            id="defer_recreate_finish",
        ),
        pytest.param(
            ["new"],
            [_keep("new"), _defer_delete, _finish("new")],
            True,
            id="keep_defer_finish",
        ),
        pytest.param(
            ["new"],
            [_defer_delete, _keep("new"), _finish("new")],
            True,
            id="defer_keep_finish",
        ),
        pytest.param(
            ["new"],
            [_defer_delete, _assert_present, _finish("new")],
            False,
            id="defer_finish",
        ),
        pytest.param(
            ["new"],
            [_defer_delete, _assert_present, _cancel("new")],
            False,
            id="defer_cancel",
        ),
        pytest.param(
            ["new"],
            [_defer_delete, _recreate, _cancel("new")],
            True,
            id="defer_recreate_cancel",
        ),
        pytest.param(
            ["new"],
            [_recreate, _defer_delete, _cancel("new")],
            True,
            id="recreate_defer_cancel",
        ),
        pytest.param(
            ["new"],
            [_finish("new"), _recreate, _defer_delete],
            False,
            id="defer_after_finish",
        ),
        pytest.param(
            ["new"],
            [_cancel("new"), _defer_delete],
            False,
            id="defer_after_cancel",
        ),
        pytest.param(
            ["old", "new"],
            [_defer_delete, _finish("old"), _assert_present, _finish("new")],
            False,
            id="overlap_newest_decides",
        ),
        pytest.param(
            ["old", "new"],
            [_recreate, _finish("new"), _defer_delete, _finish("old")],
            True,
            id="overlap_defer_after_newer_finished",
        ),
        pytest.param(
            ["old", "new"],
            [_defer_delete, _finish("old"), _assert_present, _cancel("new")],
            False,
            id="overlap_cancel_newest_applies_deferred",
        ),
        pytest.param(
            ["old", "new"],
            [_defer_delete, _cancel("old"), _assert_present, _recreate, _finish("new")],
            True,
            id="overlap_cancel_older_keeps_deferred_with_newest",
        ),
        pytest.param(
            ["old", "new"],
            [_keep("new"), _finish("new"), _finish("old")],
            True,
            id="overlap_newer_keep_binds_older",
        ),
        pytest.param(
            ["old", "new"],
            [_keep("old"), _defer_delete, _finish("new")],
            False,
            id="overlap_older_keep_does_not_bind_newer",
        ),
        pytest.param(
            ["old", "new"],
            [_cancel("new"), _assert_present, _finish("old")],
            False,
            id="overlap_older_decides_after_newer_cancelled",
        ),
        pytest.param(
            ["new"],
            [_keep_issue, _defer_delete, _finish("new")],
            True,
            id="keep_issue_defer_finish",
        ),
        pytest.param(
            ["new"],
            [_defer_delete, _keep_issue, _cancel("new")],
            True,
            id="defer_keep_issue_cancel",
        ),
        pytest.param(
            ["old", "new"],
            [_keep_issue, _cancel("new"), _finish("old")],
            True,
            id="overlap_keep_issue_binds_all",
        ),
        pytest.param(
            ["new"],
            [_finish("new"), _keep_issue, _defer_delete],
            False,
            id="keep_issue_after_finish",
        ),
    ],
)
@pytest.mark.usefixtures("issue_registry")
async def test_delete_deferred_to_refresh_sequences(
    hass: HomeAssistant,
    refresh_names: list[str],
    steps: list[_RefreshStep],
    kept: bool,
) -> None:
    """Test deferred deletes for different orders of refresh operations."""
    _create_issue(hass, "issue_1")
    ir.async_ignore_issue(hass, "test", "issue_1", True)
    refreshes = {
        name: ir.async_refresh_issues(hass, "test", issue_ids=["issue_1"])
        for name in refresh_names
    }

    for step in steps:
        step(hass, refreshes)

    # A kept issue keeps the ignore flag
    assert [
        issue.dismissed_version is not None
        for issue in ir.async_get(hass).issues.values()
    ] == [True] * kept


def _begin(name: str) -> _RefreshStep:
    def begin(hass: HomeAssistant, refreshes: dict[str, ir.IssuesRefresh]) -> None:
        refreshes[name] = ir.async_refresh_issues(hass, "test", issue_ids=["issue_1"])

    return begin


@pytest.mark.parametrize(
    ("steps", "expected"),
    [
        pytest.param(
            [_defer_delete, _keep("new"), _finish("old")],
            [{"issue_1", "issue_2"}, {"issue_1", "issue_2"}, {"issue_2"}],
            id="defer_keep_outside_scope_finish",
        ),
        pytest.param(
            [_keep("new"), _finish("old")],
            [{"issue_1", "issue_2"}, {"issue_2"}],
            id="keep_outside_scope_finish",
        ),
        pytest.param(
            [
                _defer_delete,
                _keep("new"),
                _finish("old"),
                _begin("third"),
                _cancel("third"),
            ],
            [
                {"issue_1", "issue_2"},
                {"issue_1", "issue_2"},
                {"issue_2"},
                {"issue_2"},
                {"issue_2"},
            ],
            id="defer_keep_outside_scope_finish_then_cancel_later",
        ),
    ],
)
@pytest.mark.usefixtures("issue_registry")
async def test_keep_outside_refresh_scope_disjoint_refreshes(
    hass: HomeAssistant,
    steps: list[_RefreshStep],
    expected: list[set[str]],
) -> None:
    """Test a refresh keeping an issue outside its set doesn't keep it elsewhere."""
    _create_issue(hass, "issue_1")
    _create_issue(hass, "issue_2")
    refreshes = {
        "old": ir.async_refresh_issues(hass, "test", issue_ids=["issue_1"]),
        "new": ir.async_refresh_issues(hass, "test", issue_ids=["issue_2"]),
    }
    issue_registry = ir.async_get(hass)

    after_each_step = []
    for step in steps:
        step(hass, refreshes)
        after_each_step.append({issue_id for _, issue_id in issue_registry.issues})

    assert after_each_step == expected


@pytest.mark.usefixtures("issue_registry")
async def test_delete_not_deferred_during_refresh(hass: HomeAssistant) -> None:
    """Test a plain delete during a refresh deletes immediately and unmarks."""
    _create_issue(hass, "issue_1")

    refresh = ir.async_refresh_issues(hass, "test")
    ir.async_delete_issue(hass, "test", "issue_1")
    assert ir.async_get(hass).issues == {}
    _create_issue(hass, "issue_1")
    refresh.async_finish()

    assert set(ir.async_get(hass).issues) == {("test", "issue_1")}


@pytest.mark.usefixtures("issue_registry")
async def test_keep_issue_outside_refresh(hass: HomeAssistant) -> None:
    """Test keeping an issue outside a refresh's set changes nothing."""
    _create_issue(hass, "issue_1")
    _create_issue(hass, "issue_2")
    events = async_capture_events(hass, ir.EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED)

    ir.async_keep_issue(hass, "test", "issue_1")
    refresh = ir.async_refresh_issues(hass, "test", issue_ids=["issue_2"])
    ir.async_keep_issue(hass, "test", "issue_1")
    ir.async_keep_issue(hass, "test", "unknown")
    refresh.async_finish()
    await hass.async_block_till_done()

    assert set(ir.async_get(hass).issues) == {("test", "issue_1")}
    assert [event.data for event in events] == [
        {"action": "remove", "domain": "test", "issue_id": "issue_2"}
    ]


@pytest.mark.usefixtures("issue_registry")
async def test_keep_issue_thread_safety(hass: HomeAssistant) -> None:
    """Test call async_keep_issue from a thread."""
    with pytest.raises(
        RuntimeError,
        match="Detected code that calls issue_registry.async_keep from a thread.",
    ):
        await hass.async_add_executor_job(ir.async_keep_issue, hass, "test", "any")


@pytest.mark.usefixtures("issue_registry")
async def test_refresh_issues_thread_safety(hass: HomeAssistant) -> None:
    """Test call async_refresh_issues from a thread."""
    with pytest.raises(
        RuntimeError,
        match=(
            "Detected code that calls issue_registry.async_refresh_issues from a thread."
        ),
    ):
        await hass.async_add_executor_job(
            partial(ir.async_refresh_issues, hass, "test", issue_ids=[])
        )


@pytest.mark.parametrize(
    ("method", "args"),
    [
        ("async_cancel", ()),
        ("async_finish", ()),
        ("async_keep", ([],)),
    ],
)
@pytest.mark.usefixtures("issue_registry")
async def test_issues_refresh_thread_safety(
    hass: HomeAssistant, method: str, args: tuple[Any, ...]
) -> None:
    """Test call IssuesRefresh methods from a thread."""
    refresh = ir.async_refresh_issues(hass, "test", issue_ids=[])
    with pytest.raises(
        RuntimeError,
        match=(
            f"Detected code that calls issue_registry.IssuesRefresh.{method} "
            "from a thread."
        ),
    ):
        await hass.async_add_executor_job(getattr(refresh, method), *args)
