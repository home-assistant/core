"""Test the repairs websocket API."""
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry

from tests.common import async_capture_events, flush_store


async def test_load_issues(hass: HomeAssistant) -> None:
    """Make sure that we can load/save data correctly."""
    issues = [
        {
            "breaks_in_ha_version": "2022.9",
            "domain": "test",
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
            "domain": "test",
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
            "domain": "test",
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
            "data": {"entry_id": "123"},
            "domain": "test",
            "issue_id": "issue_4",
            "is_fixable": True,
            "is_persistent": True,
            "learn_more_url": "https://checkboxrace.com/blah",
            "severity": "other",
            "translation_key": "even_worse",
            "translation_placeholders": {"xyz": "abc"},
        },
    ]

    events = async_capture_events(
        hass, issue_registry.EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED
    )

    for issue in issues:
        issue_registry.async_create_issue(
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

    assert len(events) == 4
    assert events[0].data == {
        "action": "create",
        "domain": "test",
        "issue_id": "issue_1",
    }
    assert events[1].data == {
        "action": "create",
        "domain": "test",
        "issue_id": "issue_2",
    }
    assert events[2].data == {
        "action": "create",
        "domain": "test",
        "issue_id": "issue_3",
    }
    assert events[3].data == {
        "action": "create",
        "domain": "test",
        "issue_id": "issue_4",
    }

    issue_registry.async_ignore_issue(
        hass, issues[0]["domain"], issues[0]["issue_id"], True
    )
    await hass.async_block_till_done()

    assert len(events) == 5
    assert events[4].data == {
        "action": "update",
        "domain": "test",
        "issue_id": "issue_1",
    }

    issue_registry.async_delete_issue(hass, issues[2]["domain"], issues[2]["issue_id"])
    await hass.async_block_till_done()

    assert len(events) == 6
    assert events[5].data == {
        "action": "remove",
        "domain": "test",
        "issue_id": "issue_3",
    }

    registry: issue_registry.IssueRegistry = hass.data[issue_registry.DATA_REGISTRY]
    assert len(registry.issues) == 3
    issue1 = registry.async_get_issue("test", "issue_1")
    issue2 = registry.async_get_issue("test", "issue_2")
    issue4 = registry.async_get_issue("test", "issue_4")

    registry2 = issue_registry.IssueRegistry(hass)
    await flush_store(registry._store)
    await registry2.async_load()

    assert list(registry.issues) == list(registry2.issues)

    issue1_registry2 = registry2.async_get_issue("test", "issue_1")
    assert issue1_registry2 == issue_registry.IssueEntry(
        active=False,
        breaks_in_ha_version=None,
        created=issue1.created,
        data=None,
        dismissed_version=issue1.dismissed_version,
        domain=issue1.domain,
        is_fixable=None,
        is_persistent=issue1.is_persistent,
        issue_domain=None,
        issue_id=issue1.issue_id,
        learn_more_url=None,
        severity=None,
        translation_key=None,
        translation_placeholders=None,
    )
    issue2_registry2 = registry2.async_get_issue("test", "issue_2")
    assert issue2_registry2 == issue_registry.IssueEntry(
        active=False,
        breaks_in_ha_version=None,
        created=issue2.created,
        data=None,
        dismissed_version=issue2.dismissed_version,
        domain=issue2.domain,
        is_fixable=None,
        is_persistent=issue2.is_persistent,
        issue_domain=None,
        issue_id=issue2.issue_id,
        learn_more_url=None,
        severity=None,
        translation_key=None,
        translation_placeholders=None,
    )
    issue4_registry2 = registry2.async_get_issue("test", "issue_4")
    assert issue4_registry2 == issue4


@pytest.mark.parametrize("load_registries", [False])
async def test_loading_issues_from_storage(hass: HomeAssistant, hass_storage) -> None:
    """Test loading stored issues on start."""
    hass_storage[issue_registry.STORAGE_KEY] = {
        "version": issue_registry.STORAGE_VERSION_MAJOR,
        "minor_version": issue_registry.STORAGE_VERSION_MINOR,
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
                    "created": "2022-07-19T19:41:13.746514+00:00",
                    "dismissed_version": None,
                    "domain": "test",
                    "is_persistent": False,
                    "issue_id": "issue_2",
                },
                {
                    "breaks_in_ha_version": "2022.6",
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

    await issue_registry.async_load(hass)

    registry: issue_registry.IssueRegistry = hass.data[issue_registry.DATA_REGISTRY]
    assert len(registry.issues) == 3


@pytest.mark.parametrize("load_registries", [False])
async def test_migration_1_1(hass: HomeAssistant, hass_storage) -> None:
    """Test migration from version 1.1."""
    hass_storage[issue_registry.STORAGE_KEY] = {
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

    await issue_registry.async_load(hass)

    registry: issue_registry.IssueRegistry = hass.data[issue_registry.DATA_REGISTRY]
    assert len(registry.issues) == 2
