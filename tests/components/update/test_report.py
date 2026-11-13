"""Tests for the update report."""

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.typing import WebSocketGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.update import DOMAIN, async_snapshot_before_update
from homeassistant.components.update.report import (
    STARTUP_GRACE,
    STORAGE_KEY,
    RunSnapshot,
)
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.const import __version__
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

OLD_VERSION = "2026.10.0"
CREATED = "2026-10-31T12:00:00+00:00"
NOW = "2026-11-01T12:00:00+00:00"
CORE_UPDATE = "update.home_assistant_core_update"
SENSOR = "sensor.demo_1"


def _snapshot(
    update_entity: str, version: str = OLD_VERSION, **data: Any
) -> RunSnapshot:
    return {
        "update_entity": update_entity,
        "version": version,
        "created": CREATED,
        "config_entries": {},
        "entities": {},
        "unavailable": [],
        "unknown": [],
        "issues": [],
        "upcoming": [],
    } | data


def _store(
    hass_storage: dict[str, Any],
    before_update: RunSnapshot | None,
    baseline: RunSnapshot | None = None,
    report: dict[str, Any] | None = None,
) -> None:
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "key": STORAGE_KEY,
        "data": {
            "before_update": before_update,
            "baseline": baseline,
            "report": report,
        },
    }


async def _get_report(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_id: str = CORE_UPDATE,
) -> dict[str, Any] | None:
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "update/report", "entity_id": entity_id})
    msg = await client.receive_json()
    assert msg["success"]
    return msg["result"]


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, delta: timedelta
) -> None:
    freezer.tick(delta)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def _automation(alias: str, entity_id: str) -> dict[str, Any]:
    return {
        "alias": alias,
        "triggers": {"trigger": "state", "entity_id": entity_id},
        "actions": [],
    }


@pytest.fixture(autouse=True)
def frozen_time(freezer: FrozenDateTimeFactory) -> None:
    """Freeze the time the report is made at."""
    freezer.move_to(NOW)


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
    """Return a sensor that was available in the baseline."""
    return entity_registry.async_get_or_create("sensor", "demo", "1")


@pytest.mark.parametrize(
    ("stored", "settle"),
    [
        pytest.param("before_update", False, id="pending"),
        pytest.param("before_update", True, id="settled"),
        pytest.param("baseline", False, id="pending_after_second_restart"),
    ],
)
async def test_update_report(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    entity_registry: er.EntityRegistry,
    core_update: er.RegistryEntry,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    stored: str,
    settle: bool,
) -> None:
    """Test the report lists only what got worse since the update."""
    failed = MockConfigEntry(domain="demo", title="Failed", entry_id="failed")
    failed.add_to_hass(hass)
    failed._async_set_state(
        hass,
        ConfigEntryState.SETUP_RETRY,
        "Timeout",
        error_reason_translation_key="cannot_connect",
        error_reason_translation_placeholders={"host": "1.2.3.4"},
        error_reason_translation_domain="demo",
    )
    loaded = MockConfigEntry(domain="demo", title="Loaded", entry_id="loaded")
    loaded.add_to_hass(hass)
    loaded.mock_state(hass, ConfigEntryState.LOADED)
    MockConfigEntry(
        domain="demo",
        title="Disabled",
        entry_id="disabled",
        disabled_by=ConfigEntryDisabler.USER,
    ).add_to_hass(hass)

    entities = {
        name: entity_registry.async_get_or_create(
            "sensor", "demo", name, suggested_object_id=name, config_entry=loaded
        )
        for name in (
            "healthy",
            "renamed",
            "unavailable",
            "unknown",
            "no_state",
            "unavailable_before",
            "unknown_before",
            "unknown_to_unavailable",
            "disabled",
        )
    }
    entities["of_failed_entry"] = entity_registry.async_get_or_create(
        "sensor",
        "demo",
        "of_failed_entry",
        suggested_object_id="of_failed_entry",
        config_entry=failed,
    )
    entity_registry.async_update_entity(
        "sensor.disabled", disabled_by=er.RegistryEntryDisabler.USER
    )
    for name, state in (
        ("healthy", "1"),
        ("renamed", "1"),
        ("unavailable", "unavailable"),
        ("unknown", "unknown"),
        ("unavailable_before", "unavailable"),
        ("unknown_before", "unknown"),
        ("unknown_to_unavailable", "unavailable"),
        ("of_failed_entry", "unavailable"),
        ("disabled", "unavailable"),
    ):
        hass.states.async_set(f"sensor.{name}", state)
    entity_ids = {entry.id: entry.entity_id for entry in entities.values()}
    entity_ids[entities["renamed"].id] = "sensor.old_name"
    entity_ids["gone"] = "sensor.gone"

    for issue_id, issue_domain, breaks_in_ha_version, config_entry_id in (
        ("new_issue", None, None, None),
        ("old_issue", None, None, None),
        ("ignored_issue", None, None, None),
        ("hidden_issue", None, None, "disabled"),
        ("breaks_later", DOMAIN, "2099.5.0", None),
        ("breaks_known", DOMAIN, "2099.2.0", None),
        ("breaks_known_dismissed", DOMAIN, "2099.2.0", None),
        ("breaks_sooner", DOMAIN, "2099.1.0", None),
        ("breaks_dismissed", "http", "2099.3.0", None),
        ("breaks_not_set_up", "not_set_up", "2099.1.0", None),
        ("breaks_reached", DOMAIN, "2026.1.0", None),
        ("breaks_hidden", DOMAIN, "2099.1.0", "disabled"),
    ):
        ir.async_create_issue(
            hass,
            "homeassistant",
            issue_id,
            is_fixable=False,
            issue_domain=issue_domain,
            breaks_in_ha_version=breaks_in_ha_version,
            config_entry_id=config_entry_id,
            severity=ir.IssueSeverity.WARNING,
            translation_key="country_not_configured",
        )
    ir.async_ignore_issue(hass, "homeassistant", "ignored_issue", True)
    ir.async_ignore_issue(hass, "homeassistant", "breaks_dismissed", True)
    ir.async_ignore_issue(hass, "homeassistant", "breaks_known_dismissed", True)

    old = _snapshot(
        core_update.id,
        config_entries={
            "demo": {"failed": "Failed", "loaded": "Loaded", "disabled": "Disabled"},
            "old": {"gone_entry": "Gone"},
        },
        entities={"demo": entity_ids},
        unavailable=[entities["unavailable_before"].id],
        unknown=[
            entities["unknown_before"].id,
            entities["unknown_to_unavailable"].id,
        ],
        issues=[["homeassistant", "old_issue"]],
        upcoming=[
            ["homeassistant", "breaks_known"],
            ["homeassistant", "breaks_known_dismissed"],
        ],
    )
    if stored == "before_update":
        _store(hass_storage, old)
    else:
        _store(hass_storage, None, baseline=old)

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                _automation(alias, entity_id)
                for alias, entity_id in (
                    ("Uses gone", "sensor.gone"),
                    ("Uses old name", "sensor.old_name"),
                    ("Uses new name", "sensor.renamed"),
                )
            ]
        },
    )
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "uses_old_name": {
                    "sequence": [
                        {
                            "action": "homeassistant.update_entity",
                            "target": {"entity_id": "sensor.old_name"},
                        }
                    ]
                }
            }
        },
    )
    assert await async_setup_component(hass, DOMAIN, {})
    if settle:
        await _tick(hass, freezer, STARTUP_GRACE)

    report = await _get_report(hass, hass_ws_client)

    assert report is not None
    assert report.pop("to_version") == __version__
    assert report == snapshot


async def test_references_without_automation_and_script(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    core_update: er.RegistryEntry,
) -> None:
    """Test removed entities have no references when automation and script are not set up."""
    _store(
        hass_storage,
        _snapshot(core_update.id, entities={"demo": {"gone": "sensor.gone"}}),
    )
    assert await async_setup_component(hass, DOMAIN, {})

    report = await _get_report(hass, hass_ws_client)

    assert report is not None
    assert report["entities_removed"] == [
        {
            "entity_id": "sensor.gone",
            "platform": "demo",
            "automations": [],
            "scripts": [],
        }
    ]


@pytest.mark.parametrize(
    ("baseline", "state"),
    [
        pytest.param(None, "1", id="value"),
        pytest.param("unknown", "unknown", id="unknown_before"),
        pytest.param("unavailable", "unavailable", id="unavailable_before"),
        pytest.param("unavailable", "unknown", id="unavailable_to_unknown"),
    ],
)
async def test_entity_not_worse(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    core_update: er.RegistryEntry,
    sensor: er.RegistryEntry,
    baseline: str | None,
    state: str,
) -> None:
    """Test an entity that is not worse than in the baseline is not reported."""
    _store(
        hass_storage,
        _snapshot(
            core_update.id,
            entities={"demo": {sensor.id: SENSOR}},
            **({baseline: [sensor.id]} if baseline else {}),
        ),
    )
    hass.states.async_set(SENSOR, state)
    assert await async_setup_component(hass, DOMAIN, {})

    report = await _get_report(hass, hass_ws_client)
    assert report is not None
    assert report["entities_unavailable"] == []


def _storage(data: dict[str, Any]) -> dict[str, Any]:
    return {STORAGE_KEY: {"version": 1, "key": STORAGE_KEY, "data": data}}


@pytest.mark.parametrize(
    "stored",
    [
        pytest.param({}, id="no_storage"),
        pytest.param(
            _storage({"before_update": None, "baseline": None, "report": None}),
            id="nothing_stored",
        ),
        pytest.param(
            _storage(
                {
                    "before_update": _snapshot("core", __version__),
                    "baseline": None,
                    "report": None,
                }
            ),
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

    assert await _get_report(hass, hass_ws_client) is None


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
    _store(hass_storage, _snapshot(core_update.id))
    assert await async_setup_component(hass, DOMAIN, {})

    assert await _get_report(hass, hass_ws_client, entity_id) is None
    assert await _get_report(hass, hass_ws_client) is not None


async def test_failed_update_snapshot_dropped(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    core_update: er.RegistryEntry,
) -> None:
    """Test the snapshot of an update that kept the version is not kept."""
    old = _snapshot(core_update.id)
    report = {"from_version": OLD_VERSION}
    _store(
        hass_storage,
        _snapshot(core_update.id, __version__),
        baseline=old,
        report=report,
    )
    assert await async_setup_component(hass, DOMAIN, {})

    assert hass_storage[STORAGE_KEY]["data"] == {
        "before_update": None,
        "baseline": old,
        "report": report,
    }


async def test_report_lifecycle(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    core_update: er.RegistryEntry,
    sensor: er.RegistryEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the report is made after the grace period, kept, and replaced by the next update."""
    _store(
        hass_storage,
        _snapshot(core_update.id, entities={"demo": {sensor.id: SENSOR}}),
    )
    hass.states.async_set(SENSOR, "unavailable")
    assert await async_setup_component(hass, DOMAIN, {})

    await _tick(hass, freezer, STARTUP_GRACE - timedelta(seconds=1))
    report = await _get_report(hass, hass_ws_client)
    assert report is not None
    assert report["pending"] is True
    assert report["created"] is None
    assert hass_storage[STORAGE_KEY]["data"]["report"] is None

    await _tick(hass, freezer, timedelta(seconds=1))
    report = await _get_report(hass, hass_ws_client)
    assert report is not None
    assert report["pending"] is False
    assert report["created"] == "2026-11-01T12:05:00+00:00"
    assert len(report["entities_unavailable"]) == 1
    stored = hass_storage[STORAGE_KEY]["data"]
    assert stored["report"]["created"] == report["created"]

    # The stored report does not change when the entity recovers.
    hass.states.async_set(SENSOR, "1")
    assert await _get_report(hass, hass_ws_client) == report


async def test_new_baseline_replaces_report(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    core_update: er.RegistryEntry,
) -> None:
    """Test the snapshot of a new update replaces the previous report."""
    new = _snapshot(core_update.id, "2026.11.0")
    _store(
        hass_storage,
        new,
        baseline=_snapshot(core_update.id),
        report={"from_version": OLD_VERSION},
    )
    assert await async_setup_component(hass, DOMAIN, {})

    assert hass_storage[STORAGE_KEY]["data"] == {
        "before_update": None,
        "baseline": new,
        "report": None,
    }
    report = await _get_report(hass, hass_ws_client)
    assert report is not None
    assert report["from_version"] == "2026.11.0"
    assert report["pending"] is True


async def test_snapshot_before_update(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    entity_registry: er.EntityRegistry,
    core_update: er.RegistryEntry,
    sensor: er.RegistryEntry,
) -> None:
    """Test the snapshot before an update is saved next to the current report."""
    hass.states.async_set(SENSOR, "1")
    unavailable = entity_registry.async_get_or_create(
        "sensor", "demo", "unavailable", suggested_object_id="unavailable"
    )
    hass.states.async_set("sensor.unavailable", "unavailable")
    unknown = entity_registry.async_get_or_create(
        "sensor", "demo", "unknown", suggested_object_id="unknown"
    )
    hass.states.async_set("sensor.unknown", "unknown")
    entity_registry.async_get_or_create(
        "sensor", "demo", "disabled", disabled_by=er.RegistryEntryDisabler.USER
    )
    entry = MockConfigEntry(domain="demo", title="Demo", entry_id="demo_entry")
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    ir.async_create_issue(
        hass,
        "homeassistant",
        "issue",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="country_not_configured",
    )
    ir.async_create_issue(
        hass,
        "homeassistant",
        "breaks_ignored",
        is_fixable=False,
        breaks_in_ha_version="2099.1.0",
        severity=ir.IssueSeverity.WARNING,
        translation_key="country_not_configured",
    )
    ir.async_ignore_issue(hass, "homeassistant", "breaks_ignored", True)
    old = _snapshot(core_update.id)
    _store(hass_storage, None, baseline=old)
    assert await async_setup_component(hass, DOMAIN, {})

    await async_snapshot_before_update(hass, CORE_UPDATE)

    data = hass_storage[STORAGE_KEY]["data"]
    assert data["baseline"] == old
    assert data["before_update"] == {
        "update_entity": core_update.id,
        "version": __version__,
        "created": NOW,
        "config_entries": {"demo": {"demo_entry": "Demo"}},
        "entities": {
            "hassio": {core_update.id: CORE_UPDATE},
            "demo": {
                sensor.id: SENSOR,
                unavailable.id: "sensor.unavailable",
                unknown.id: "sensor.unknown",
            },
        },
        "unavailable": [core_update.id, unavailable.id],
        "unknown": [unknown.id],
        "issues": [["homeassistant", "issue"]],
        "upcoming": [["homeassistant", "breaks_ignored"]],
    }


async def test_snapshot_skipped_for_unknown_entity(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test no snapshot is saved for an update entity that is not registered."""
    assert await async_setup_component(hass, DOMAIN, {})

    await async_snapshot_before_update(hass, CORE_UPDATE)

    assert STORAGE_KEY not in hass_storage


async def test_report_requires_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
    hass_storage: dict[str, Any],
    core_update: er.RegistryEntry,
) -> None:
    """Test a non-admin user can't read the report."""
    _store(hass_storage, _snapshot(core_update.id))
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_ws_client(hass, hass_read_only_access_token)

    await client.send_json_auto_id({"type": "update/report", "entity_id": CORE_UPDATE})
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "unauthorized"
