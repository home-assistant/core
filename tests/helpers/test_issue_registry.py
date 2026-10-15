"""Test the repairs websocket API."""

import asyncio
import dataclasses
from functools import partial
from typing import Any

import pytest

from homeassistant.config_entries import ConfigEntryDisabler
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_capture_events, flush_store


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
