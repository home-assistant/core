"""Tests for the update report."""

from collections.abc import Generator
from datetime import timedelta
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.typing import WebSocketGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.update import (
    DOMAIN,
    async_discard_snapshot,
    async_snapshot_before_update,
)
from homeassistant.components.update.report import (
    MAX_REPORTS,
    STARTUP_GRACE,
    STORAGE_KEY,
    Report,
    RunSnapshot,
)
from homeassistant.config_entries import ConfigEntryDisabler
from homeassistant.const import __version__
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

OLD_VERSION = "2026.10.0"
CREATED = "2026-10-31T12:00:00+00:00"
STARTED = "2026-10-31T12:10:00+00:00"
NOW = "2026-11-01T12:00:00+00:00"
SETTLED = "2026-11-01T12:05:00+00:00"
CORE_UPDATE = "update.home_assistant_core_update"
SENSOR = "sensor.demo_1"
REPORT_ID = "01KA0000000000000000000000"


def _snapshot(
    update_entity: str, version: str = OLD_VERSION, **data: Any
) -> RunSnapshot:
    return {
        "update_entity": update_entity,
        "version": version,
        "created": CREATED,
        "backup": False,
        "automatic": False,
        "entities": {},
        "issues": [],
    } | data


def _report(report_id: str, **data: Any) -> Report:
    return {
        "id": report_id,
        "from_version": OLD_VERSION,
        "to_version": "2026.10.1",
        "update_started": CREATED,
        "backup": False,
        "automatic": False,
        "started": STARTED,
        "created": CREATED,
        "pending": False,
        "severity": None,
        "issues": [],
    } | data


def _storage(
    before_update: RunSnapshot | None = None,
    pending: RunSnapshot | None = None,
    reports: dict[str, list[Report]] | None = None,
    started: str | None = None,
) -> dict[str, Any]:
    return {
        STORAGE_KEY: {
            "version": 1,
            "key": STORAGE_KEY,
            "data": {
                "before_update": before_update,
                "pending": pending
                and {"id": REPORT_ID, "baseline": pending, "started": started},
                "reports": reports or {},
            },
        }
    }


def _store(
    hass_storage: dict[str, Any],
    before_update: RunSnapshot | None = None,
    pending: RunSnapshot | None = None,
    reports: dict[str, list[Report]] | None = None,
    started: str | None = None,
) -> None:
    hass_storage.update(_storage(before_update, pending, reports, started))


async def _get_reports(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_id: str = CORE_UPDATE,
) -> list[dict[str, Any]]:
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "update/reports", "entity_id": entity_id})
    msg = await client.receive_json()
    assert msg["success"]
    return msg["result"]


async def _get_report(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_id: str = CORE_UPDATE,
    report_id: str = REPORT_ID,
) -> dict[str, Any] | None:
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "update/report", "entity_id": entity_id, "report_id": report_id}
    )
    msg = await client.receive_json()
    assert msg["success"]
    return msg["result"]


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, delta: timedelta
) -> None:
    freezer.tick(delta)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def _automation(alias: str, entity_id: str, **config: Any) -> dict[str, Any]:
    return {
        "alias": alias,
        "triggers": {"trigger": "state", "entity_id": entity_id},
        "actions": [],
        **config,
    }


def _script(entity_id: str) -> dict[str, Any]:
    return {
        "sequence": [
            {
                "action": "homeassistant.update_entity",
                "target": {"entity_id": entity_id},
            }
        ]
    }


def _create_issue(
    hass: HomeAssistant,
    issue_id: str,
    severity: ir.IssueSeverity = ir.IssueSeverity.WARNING,
    **kwargs: Any,
) -> None:
    ir.async_create_issue(
        hass,
        "homeassistant",
        issue_id,
        is_fixable=False,
        severity=severity,
        translation_key="country_not_configured",
        **kwargs,
    )


@pytest.fixture(autouse=True)
def frozen_time(freezer: FrozenDateTimeFactory) -> None:
    """Freeze the time the report is made at."""
    freezer.move_to(NOW)


@pytest.fixture(autouse=True)
def report_id() -> Generator[None]:
    """Give new reports a fixed id."""
    with patch(
        "homeassistant.components.update.report.ulid_now", return_value=REPORT_ID
    ):
        yield


@pytest.fixture
def core_update(entity_registry: er.EntityRegistry) -> er.RegistryEntry:
    """Return the registry entry of the Core update entity."""
    return entity_registry.async_get_or_create(
        DOMAIN,
        "hassio",
        "home_assistant_core_version_latest",
        suggested_object_id="home_assistant_core_update",
    )


@pytest.fixture
def sensor(entity_registry: er.EntityRegistry) -> er.RegistryEntry:
    """Return a sensor that existed in the baseline."""
    return entity_registry.async_get_or_create("sensor", "demo", "1")


@pytest.mark.parametrize(
    ("stored", "started", "settle"),
    [
        pytest.param("before_update", None, False, id="pending"),
        pytest.param("before_update", None, True, id="settled"),
        pytest.param("pending", STARTED, False, id="pending_after_second_restart"),
    ],
)
async def test_update_report(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    core_update: er.RegistryEntry,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    stored: str,
    started: str | None,
    settle: bool,
) -> None:
    """Test the report lists the issues that appeared since the update."""
    MockConfigEntry(
        domain="demo", entry_id="disabled", disabled_by=ConfigEntryDisabler.USER
    ).add_to_hass(hass)
    entities = {
        name: entity_registry.async_get_or_create(
            "sensor", "demo", name, suggested_object_id=name
        )
        for name in ("healthy", "renamed", "renamed_unreferenced", "replaced")
    }
    entity_ids = {entry.id: entry.entity_id for entry in entities.values()}
    entity_ids[entities["renamed"].id] = "sensor.old_name"
    entity_ids[entities["renamed_unreferenced"].id] = "sensor.old_unreferenced"
    entity_ids["gone"] = "sensor.gone"
    entity_ids["gone_unreferenced"] = "sensor.gone_unreferenced"
    # A new registry entry took the entity ID over
    entity_ids["replaced_before"] = "sensor.replaced"
    # No registry entry anymore, but still a state
    entity_ids["state_only"] = "sensor.state_only"
    hass.states.async_set("sensor.state_only", "1")

    _create_issue(hass, "new_issue")
    _create_issue(hass, "new_error", ir.IssueSeverity.ERROR)
    _create_issue(hass, "old_issue")
    _create_issue(hass, "ignored_issue")
    _create_issue(hass, "hidden_issue", config_entry_id="disabled")
    ir.async_ignore_issue(hass, "homeassistant", "ignored_issue", True)

    old = _snapshot(
        core_update.id,
        backup=True,
        automatic=True,
        entities={"demo": entity_ids},
        issues=[["homeassistant", "old_issue"]],
    )
    _store(hass_storage, started=started, **{stored: old})

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                _automation("Uses gone", "sensor.gone", id="uses_gone"),
                _automation("Uses old name", "sensor.old_name"),
                _automation("Uses new name", "sensor.renamed"),
                _automation("Uses replaced", "sensor.replaced"),
                _automation("Uses state only", "sensor.state_only"),
            ]
        },
    )
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "uses_gone": _script("sensor.gone"),
                "uses_old_name": _script("sensor.old_name"),
            }
        },
    )
    assert await async_setup_component(hass, DOMAIN, {})
    if settle:
        await _tick(hass, freezer, STARTUP_GRACE)

    reports = await _get_reports(hass, hass_ws_client)
    report = await _get_report(hass, hass_ws_client)

    assert report is not None
    assert report.pop("to_version") == __version__
    assert reports[0].pop("to_version") == __version__
    assert reports == snapshot(name="reports")
    assert report == snapshot(name="report")
    stale_issues = {
        issue_id: issue
        for (domain, issue_id), issue in issue_registry.issues.items()
        if domain == DOMAIN
    }
    placeholders = {
        issue_id: dict(issue.translation_placeholders or {})
        for issue_id, issue in stale_issues.items()
    }
    # Kept out of the snapshot: the version changes every release
    assert [p.pop("to_version") for p in placeholders.values()] == [__version__] * len(
        stale_issues
    )
    assert {
        issue_id: {
            "translation_key": issue.translation_key,
            "severity": issue.severity,
            "is_persistent": issue.is_persistent,
            "translation_placeholders": placeholders[issue_id],
        }
        for issue_id, issue in stale_issues.items()
    } == snapshot(name="issues")


STALE_ISSUE = "stale_entity_automation.uses_gone_sensor.gone"


async def _reload(hass: HomeAssistant, domain: str, config: Any) -> None:
    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={domain: config},
    ):
        await hass.services.async_call(domain, "reload", blocking=True)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("config", "entity_back", "cleared"),
    [
        pytest.param(
            [_automation("Uses other", "sensor.other", id="uses_gone")],
            False,
            True,
            id="fixed",
        ),
        pytest.param(
            [_automation("Uses gone", "sensor.gone", id="uses_gone")],
            False,
            False,
            id="still_stale",
        ),
        pytest.param(
            [_automation("Uses gone", "sensor.gone", id="uses_gone")],
            True,
            True,
            id="entity_back",
        ),
        pytest.param([], False, True, id="deleted"),
    ],
)
async def test_stale_reference_issue_cleared(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    core_update: er.RegistryEntry,
    freezer: FrozenDateTimeFactory,
    config: list[dict[str, Any]],
    entity_back: bool,
    cleared: bool,
) -> None:
    """Test the stale reference issue goes away once the automation is fixed."""
    _store(
        hass_storage,
        pending=_snapshot(core_update.id, entities={"demo": {"gone": "sensor.gone"}}),
    )
    assert await async_setup_component(
        hass,
        "automation",
        {"automation": [_automation("Uses gone", "sensor.gone", id="uses_gone")]},
    )
    assert await async_setup_component(hass, DOMAIN, {})
    await _tick(hass, freezer, STARTUP_GRACE)
    assert issue_registry.async_get_issue(DOMAIN, STALE_ISSUE)

    if entity_back:
        hass.states.async_set("sensor.gone", "1")
    if not config:
        entity_registry.async_remove("automation.uses_gone")
    await _reload(hass, "automation", config)

    assert (issue_registry.async_get_issue(DOMAIN, STALE_ISSUE) is None) == cleared


async def test_stale_reference_issue_cleared_for_script(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
    core_update: er.RegistryEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the stale reference issue goes away once the script is fixed."""
    _store(
        hass_storage,
        pending=_snapshot(core_update.id, entities={"demo": {"gone": "sensor.gone"}}),
    )
    assert await async_setup_component(
        hass, "script", {"script": {"uses_gone": _script("sensor.gone")}}
    )
    assert await async_setup_component(hass, DOMAIN, {})
    await _tick(hass, freezer, STARTUP_GRACE)
    issue_id = "stale_entity_script.uses_gone_sensor.gone"
    assert issue_registry.async_get_issue(DOMAIN, issue_id)

    await _reload(hass, "script", {"uses_gone": _script("sensor.other")})

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_stale_reference_issue_cleared_at_next_report(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
    core_update: er.RegistryEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a stale reference issue fixed while Home Assistant was down is removed."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        STALE_ISSUE,
        is_fixable=False,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="stale_entity_removed",
        translation_placeholders={
            "name": "Uses gone",
            "kind_entity_id": "automation.uses_gone",
            "old_entity_id": "sensor.gone",
            "to_version": OLD_VERSION,
            "edit": "/config/automation/edit/uses_gone",
        },
    )
    _store(hass_storage, pending=_snapshot(core_update.id))
    assert await async_setup_component(
        hass,
        "automation",
        {"automation": [_automation("Uses other", "sensor.other", id="uses_gone")]},
    )
    assert await async_setup_component(hass, DOMAIN, {})
    await _tick(hass, freezer, STARTUP_GRACE)

    assert issue_registry.async_get_issue(DOMAIN, STALE_ISSUE) is None


async def test_stale_references_without_automation_and_script(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
    core_update: er.RegistryEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a removed entity makes no issue when automation and script are not set up."""
    _store(
        hass_storage,
        pending=_snapshot(core_update.id, entities={"demo": {"gone": "sensor.gone"}}),
    )
    assert await async_setup_component(hass, DOMAIN, {})
    await _tick(hass, freezer, STARTUP_GRACE)

    assert not issue_registry.issues


@pytest.mark.parametrize(
    ("baseline", "issues", "severity", "count"),
    [
        pytest.param({}, [], None, 0, id="nothing_new"),
        pytest.param({}, [ir.IssueSeverity.ERROR], "error", 1, id="error"),
        pytest.param({}, [ir.IssueSeverity.CRITICAL], "error", 1, id="critical"),
        pytest.param({}, [ir.IssueSeverity.WARNING], "warning", 1, id="warning"),
        pytest.param(
            {},
            [ir.IssueSeverity.WARNING, ir.IssueSeverity.ERROR],
            "error",
            2,
            id="warning_and_error",
        ),
        pytest.param(
            {"entities": {"demo": {"gone": "sensor.gone"}}},
            [],
            None,
            0,
            id="unreferenced_entity_removed",
        ),
    ],
)
async def test_severity(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    core_update: er.RegistryEntry,
    freezer: FrozenDateTimeFactory,
    baseline: dict[str, Any],
    issues: list[ir.IssueSeverity],
    severity: str | None,
    count: int,
) -> None:
    """Test the severity and issue count of a report come from the new issues."""
    for index, issue_severity in enumerate(issues):
        _create_issue(hass, f"issue_{index}", issue_severity)
    _store(hass_storage, pending=_snapshot(core_update.id, **baseline))
    assert await async_setup_component(hass, DOMAIN, {})
    await _tick(hass, freezer, STARTUP_GRACE)

    reports = await _get_reports(hass, hass_ws_client)

    assert [(report["severity"], report["issues"]) for report in reports] == [
        (severity, count)
    ]


@pytest.mark.parametrize(
    "stored",
    [
        pytest.param({}, id="no_storage"),
        pytest.param(_storage(), id="nothing_stored"),
        pytest.param(
            _storage(before_update=_snapshot("core", __version__)),
            id="update_failed",
        ),
    ],
)
async def test_no_report(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    stored: dict[str, Any],
) -> None:
    """Test there is no report without an update."""
    hass_storage.update(stored)
    assert await async_setup_component(hass, DOMAIN, {})
    await _tick(hass, freezer, STARTUP_GRACE)

    assert await _get_reports(hass, hass_ws_client) == []
    assert await _get_report(hass, hass_ws_client) is None


@pytest.mark.parametrize(
    ("entity_id", "report_id"),
    [
        pytest.param(CORE_UPDATE, "unknown", id="unknown_report"),
        pytest.param(CORE_UPDATE, "stored", id="stored"),
        pytest.param("update.other", REPORT_ID, id="other_entity"),
    ],
)
async def test_report_by_id(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    entity_registry: er.EntityRegistry,
    core_update: er.RegistryEntry,
    snapshot: SnapshotAssertion,
    entity_id: str,
    report_id: str,
) -> None:
    """Test a report is only returned for its own id and update entity."""
    other = entity_registry.async_get_or_create(
        DOMAIN, "demo", "other", suggested_object_id="other"
    )
    _store(
        hass_storage,
        pending=_snapshot(core_update.id),
        reports={
            core_update.id: [_report("stored")],
            other.id: [_report("other")],
        },
    )
    assert await async_setup_component(hass, DOMAIN, {})

    assert await _get_report(hass, hass_ws_client, entity_id, report_id) == snapshot


@pytest.mark.parametrize(
    "entity_id",
    [
        pytest.param("update.other", id="other_entity"),
        pytest.param("update.not_registered", id="not_registered"),
    ],
)
async def test_no_report_for_other_entity(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    entity_registry: er.EntityRegistry,
    core_update: er.RegistryEntry,
    entity_id: str,
) -> None:
    """Test the report is only returned for the entity it belongs to."""
    entity_registry.async_get_or_create(
        DOMAIN, "demo", "other", suggested_object_id="other"
    )
    _store(hass_storage, pending=_snapshot(core_update.id))
    assert await async_setup_component(hass, DOMAIN, {})

    assert await _get_reports(hass, hass_ws_client, entity_id) == []
    assert len(await _get_reports(hass, hass_ws_client)) == 1


async def test_failed_update_snapshot_dropped(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    core_update: er.RegistryEntry,
) -> None:
    """Test the snapshot of an update that kept the version is not kept."""
    reports = {core_update.id: [_report("stored")]}
    _store(
        hass_storage,
        before_update=_snapshot(core_update.id, __version__),
        reports=reports,
    )
    assert await async_setup_component(hass, DOMAIN, {})

    assert hass_storage[STORAGE_KEY]["data"] == {
        "before_update": None,
        "pending": None,
        "reports": reports,
    }


async def test_report_lifecycle(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    core_update: er.RegistryEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the report is made after the grace period and then kept as it was."""
    _store(
        hass_storage,
        before_update=_snapshot(core_update.id, backup=True, automatic=True),
    )
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    _create_issue(hass, "new_issue")

    await _tick(hass, freezer, STARTUP_GRACE - timedelta(seconds=1))
    report = await _get_report(hass, hass_ws_client)
    assert report == {
        "id": REPORT_ID,
        "from_version": OLD_VERSION,
        "to_version": __version__,
        "update_started": CREATED,
        "backup": True,
        "automatic": True,
        "started": NOW,
        "created": None,
        "pending": True,
        "severity": "warning",
        "issues": [
            {
                "domain": "homeassistant",
                "issue_id": "new_issue",
                "severity": "warning",
            }
        ],
    }
    stored = hass_storage[STORAGE_KEY]["data"]
    assert stored["pending"]["started"] == NOW
    assert stored["reports"] == {}

    await _tick(hass, freezer, timedelta(seconds=1))
    report = await _get_report(hass, hass_ws_client)
    assert report is not None
    assert report["pending"] is False
    assert report["started"] == NOW
    assert report["created"] == SETTLED
    assert report["severity"] == "warning"
    stored = hass_storage[STORAGE_KEY]["data"]
    assert stored["pending"] is None
    assert stored["reports"][core_update.id][0]["created"] == SETTLED

    # The stored report does not change when the issue is resolved.
    ir.async_delete_issue(hass, "homeassistant", "new_issue")
    assert await _get_report(hass, hass_ws_client) == report


async def test_history(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    core_update: er.RegistryEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a new report goes first and the oldest beyond the limit is dropped."""
    old_reports = [_report(f"report_{index}") for index in range(MAX_REPORTS)]
    _store(
        hass_storage,
        before_update=_snapshot(core_update.id, "2026.11.0"),
        reports={core_update.id: old_reports},
    )
    assert await async_setup_component(hass, DOMAIN, {})

    pending_ids = [report["id"] for report in await _get_reports(hass, hass_ws_client)]
    await _tick(hass, freezer, STARTUP_GRACE)
    settled = await _get_reports(hass, hass_ws_client)

    expected_ids = [REPORT_ID, *(report["id"] for report in old_reports[:-1])]
    assert pending_ids == expected_ids
    assert [report["id"] for report in settled] == expected_ids
    assert settled[0]["from_version"] == "2026.11.0"
    assert [
        report["id"]
        for report in hass_storage[STORAGE_KEY]["data"]["reports"][core_update.id]
    ] == expected_ids


async def test_next_update_finishes_pending_report(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    core_update: er.RegistryEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test updating again within the grace period finishes the pending report."""
    _store(hass_storage, pending=_snapshot(core_update.id))
    _create_issue(hass, "new_issue")
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    await async_snapshot_before_update(hass, CORE_UPDATE, backup=False, automatic=True)
    ir.async_delete_issue(hass, "homeassistant", "new_issue")
    await _tick(hass, freezer, STARTUP_GRACE)

    data = hass_storage[STORAGE_KEY]["data"]
    assert data["pending"] is None
    assert data["before_update"]["version"] == __version__
    assert await _get_reports(hass, hass_ws_client) == [
        {
            "id": REPORT_ID,
            "from_version": OLD_VERSION,
            "to_version": __version__,
            "update_started": CREATED,
            "created": NOW,
            "pending": False,
            "severity": "warning",
            "automatic": False,
            "issues": 1,
        }
    ]


async def test_discard_snapshot(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    core_update: er.RegistryEntry,
) -> None:
    """Test the snapshot of an update that did not start is forgotten."""
    reports = {core_update.id: [_report("stored")]}
    _store(hass_storage, reports=reports)
    assert await async_setup_component(hass, DOMAIN, {})
    await async_snapshot_before_update(hass, CORE_UPDATE, backup=True, automatic=True)

    await async_discard_snapshot(hass)

    assert hass_storage[STORAGE_KEY]["data"] == {
        "before_update": None,
        "pending": None,
        "reports": reports,
    }


@pytest.mark.parametrize(
    ("backup", "automatic"),
    [
        pytest.param(False, False, id="manual"),
        pytest.param(True, True, id="automatic_with_backup"),
    ],
)
async def test_snapshot_before_update(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    entity_registry: er.EntityRegistry,
    core_update: er.RegistryEntry,
    sensor: er.RegistryEntry,
    backup: bool,
    automatic: bool,
) -> None:
    """Test the snapshot before an update is saved next to the current report."""
    entity_registry.async_get_or_create(
        "sensor", "demo", "disabled", disabled_by=er.RegistryEntryDisabler.USER
    )
    MockConfigEntry(
        domain="demo", entry_id="disabled", disabled_by=ConfigEntryDisabler.USER
    ).add_to_hass(hass)
    _create_issue(hass, "issue")
    _create_issue(hass, "ignored")
    _create_issue(hass, "hidden", config_entry_id="disabled")
    ir.async_ignore_issue(hass, "homeassistant", "ignored", True)
    reports = {core_update.id: [_report("stored")]}
    _store(hass_storage, reports=reports)
    assert await async_setup_component(hass, DOMAIN, {})

    await async_snapshot_before_update(
        hass, CORE_UPDATE, backup=backup, automatic=automatic
    )

    data = hass_storage[STORAGE_KEY]["data"]
    assert data["reports"] == reports
    assert data["before_update"] == {
        "update_entity": core_update.id,
        "version": __version__,
        "created": NOW,
        "backup": backup,
        "automatic": automatic,
        "entities": {
            "hassio": {core_update.id: CORE_UPDATE},
            "demo": {sensor.id: SENSOR},
        },
        "issues": [["homeassistant", "issue"]],
    }


async def test_snapshot_skipped_for_unknown_entity(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test no snapshot is saved for an update entity that is not registered."""
    assert await async_setup_component(hass, DOMAIN, {})

    await async_snapshot_before_update(hass, CORE_UPDATE, backup=False, automatic=False)

    assert STORAGE_KEY not in hass_storage


@pytest.mark.parametrize(
    "command",
    [
        pytest.param({"type": "update/reports"}, id="reports"),
        pytest.param({"type": "update/report", "report_id": REPORT_ID}, id="report"),
    ],
)
async def test_report_requires_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
    hass_storage: dict[str, Any],
    core_update: er.RegistryEntry,
    command: dict[str, Any],
) -> None:
    """Test a non-admin user can't read the reports."""
    _store(hass_storage, pending=_snapshot(core_update.id))
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_ws_client(hass, hass_read_only_access_token)

    await client.send_json_auto_id(command | {"entity_id": CORE_UPDATE})
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "unauthorized"
