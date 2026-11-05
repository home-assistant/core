"""Tests for the update report."""

from datetime import timedelta
from http import HTTPStatus
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.typing import ClientSessionGenerator, WebSocketGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.repairs import async_snapshot_before_update
from homeassistant.components.repairs.const import DOMAIN, UPDATE_REPORT_ISSUE_ID
from homeassistant.components.repairs.update_report import (
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
SENSOR = "sensor.demo_1"


def _snapshot(version: str = OLD_VERSION, **data: Any) -> RunSnapshot:
    return {
        "version": version,
        "created": CREATED,
        "config_entries": {},
        "entities": {},
        "unhealthy": [],
        "issues": [],
    } | data


def _store(
    hass_storage: dict[str, Any],
    before_update: RunSnapshot | None,
    baseline: RunSnapshot | None = None,
) -> None:
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "key": STORAGE_KEY,
        "data": {"before_update": before_update, "baseline": baseline},
    }


async def _get_report(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> dict[str, Any] | None:
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "repairs/update_report"})
    msg = await client.receive_json()
    assert msg["success"]
    return msg["result"]


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, delta: timedelta
) -> None:
    freezer.tick(delta)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.fixture
def sensor(entity_registry: er.EntityRegistry) -> er.RegistryEntry:
    """Return a sensor that was available in the baseline."""
    return entity_registry.async_get_or_create("sensor", "demo", "1")


@pytest.mark.parametrize(
    "stored",
    [
        pytest.param("before_update", id="first_run_after_update"),
        pytest.param("baseline", id="baseline_kept_after_second_restart"),
    ],
)
async def test_update_report(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    stored: str,
) -> None:
    """Test the report lists only what got worse since the update."""
    failed = MockConfigEntry(domain="demo", title="Failed", entry_id="failed")
    failed.add_to_hass(hass)
    failed.mock_state(hass, ConfigEntryState.SETUP_RETRY, reason="Timeout")
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
            "unhealthy_before",
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
        ("unhealthy_before", "unavailable"),
        ("of_failed_entry", "unavailable"),
        ("disabled", "unavailable"),
    ):
        hass.states.async_set(f"sensor.{name}", state)
    entity_ids = {entry.id: entry.entity_id for entry in entities.values()}
    entity_ids[entities["renamed"].id] = "sensor.old_name"
    entity_ids["gone"] = "sensor.gone"

    for issue_id, issue_domain, breaks_in_ha_version in (
        ("new_issue", None, None),
        ("old_issue", None, None),
        ("ignored_issue", None, None),
        ("breaks_later", "repairs", "2027.5.0"),
        ("breaks_sooner", "repairs", "2026.12.0"),
        ("breaks_dismissed", "http", "2027.1.0"),
        ("breaks_not_set_up", "not_set_up", "2026.12.0"),
    ):
        ir.async_create_issue(
            hass,
            "homeassistant",
            issue_id,
            is_fixable=False,
            issue_domain=issue_domain,
            breaks_in_ha_version=breaks_in_ha_version,
            severity=ir.IssueSeverity.WARNING,
            translation_key="country_not_configured",
        )
    ir.async_ignore_issue(hass, "homeassistant", "ignored_issue", True)
    ir.async_ignore_issue(hass, "homeassistant", "breaks_dismissed", True)

    old = _snapshot(
        config_entries={
            "demo": {"failed": "Failed", "loaded": "Loaded", "disabled": "Disabled"},
            "old": {"gone_entry": "Gone"},
        },
        entities={"demo": entity_ids},
        unhealthy=[entities["unhealthy_before"].id],
        issues=[
            ["homeassistant", issue_id]
            for issue_id in (
                "old_issue",
                "breaks_later",
                "breaks_sooner",
                "breaks_not_set_up",
            )
        ],
    )
    _store(
        hass_storage,
        **{
            "before_update": {"before_update": old},
            "baseline": {"before_update": None, "baseline": old},
        }[stored],
    )

    assert await async_setup_component(hass, DOMAIN, {})

    assert await _get_report(hass, hass_ws_client) == snapshot


@pytest.mark.parametrize(
    "stored",
    [
        pytest.param({}, id="no_storage"),
        pytest.param(
            {
                STORAGE_KEY: {
                    "version": 1,
                    "key": STORAGE_KEY,
                    "data": {"before_update": None, "baseline": None},
                }
            },
            id="nothing_stored",
        ),
        pytest.param(
            {
                STORAGE_KEY: {
                    "version": 1,
                    "key": STORAGE_KEY,
                    "data": {
                        "before_update": _snapshot(__version__),
                        "baseline": None,
                    },
                }
            },
            id="update_failed",
        ),
    ],
)
async def test_no_report(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
    stored: dict[str, Any],
) -> None:
    """Test there is no report without an update."""
    hass_storage.update(stored)
    assert await async_setup_component(hass, DOMAIN, {})
    await _tick(hass, freezer, STARTUP_GRACE)

    assert await _get_report(hass, hass_ws_client) is None
    assert not issue_registry.async_get_issue(DOMAIN, UPDATE_REPORT_ISSUE_ID)


async def test_failed_update_snapshot_dropped(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test the snapshot of an update that kept the version is not kept."""
    old = _snapshot()
    _store(hass_storage, _snapshot(__version__), baseline=old)
    assert await async_setup_component(hass, DOMAIN, {})

    assert hass_storage[STORAGE_KEY]["data"] == {
        "baseline": old,
        "before_update": None,
    }


async def test_issue_lifecycle(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
    sensor: er.RegistryEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the issue is raised after the grace period."""
    _store(hass_storage, _snapshot(entities={"demo": {sensor.id: SENSOR}}))
    hass.states.async_set(SENSOR, "unavailable")
    assert await async_setup_component(hass, DOMAIN, {})

    await _tick(hass, freezer, STARTUP_GRACE - timedelta(seconds=1))
    assert not issue_registry.async_get_issue(DOMAIN, UPDATE_REPORT_ISSUE_ID)

    await _tick(hass, freezer, timedelta(seconds=1))
    issue = issue_registry.async_get_issue(DOMAIN, UPDATE_REPORT_ISSUE_ID)
    assert issue
    assert issue.is_fixable
    assert issue.translation_placeholders == {
        "from_version": OLD_VERSION,
        "to_version": __version__,
        "config_entries": "0",
        "entities": "1",
        "issues": "0",
    }


async def test_no_issue_when_nothing_changed(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
    sensor: er.RegistryEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test no issue is raised when nothing got worse."""
    _store(hass_storage, _snapshot(entities={"demo": {sensor.id: SENSOR}}))
    hass.states.async_set(SENSOR, "1")
    assert await async_setup_component(hass, DOMAIN, {})
    await _tick(hass, freezer, STARTUP_GRACE)

    assert not issue_registry.async_get_issue(DOMAIN, UPDATE_REPORT_ISSUE_ID)
    assert await _get_report(hass, hass_ws_client) == {
        "from_version": OLD_VERSION,
        "to_version": __version__,
        "created": CREATED,
        "config_entries": [],
        "entities_unavailable": [],
        "entities_renamed": [],
        "entities_removed": [],
        "issues": [],
        "upcoming": [],
    }


async def test_snapshot_before_update(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    entity_registry: er.EntityRegistry,
    sensor: er.RegistryEntry,
) -> None:
    """Test the snapshot before an update becomes the baseline and is saved anew."""
    old = _snapshot()
    _store(hass_storage, old)
    hass.states.async_set(SENSOR, "1")
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
    assert await async_setup_component(hass, DOMAIN, {})
    assert hass_storage[STORAGE_KEY]["data"] == {
        "baseline": old,
        "before_update": None,
    }

    await async_snapshot_before_update(hass)

    data = hass_storage[STORAGE_KEY]["data"]
    assert data["baseline"] == old
    assert data["before_update"] == {
        "version": __version__,
        "created": data["before_update"]["created"],
        "config_entries": {"demo": {"demo_entry": "Demo"}},
        "entities": {"demo": {sensor.id: SENSOR}},
        "unhealthy": [],
        "issues": [["homeassistant", "issue"]],
    }


async def test_dismiss(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
    sensor: er.RegistryEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test dismissing the report removes the baseline and the issue."""
    _store(hass_storage, _snapshot(entities={"demo": {sensor.id: SENSOR}}))
    assert await async_setup_component(hass, DOMAIN, {})
    await _tick(hass, freezer, STARTUP_GRACE)
    assert issue_registry.async_get_issue(DOMAIN, UPDATE_REPORT_ISSUE_ID)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "repairs/update_report/dismiss"})
    assert (await client.receive_json())["success"]
    await _tick(hass, freezer, timedelta(seconds=1))

    assert hass_storage[STORAGE_KEY]["data"]["baseline"] is None
    assert not issue_registry.async_get_issue(DOMAIN, UPDATE_REPORT_ISSUE_ID)
    assert await _get_report(hass, hass_ws_client) is None


@pytest.mark.parametrize(
    "command", ["repairs/update_report", "repairs/update_report/dismiss"]
)
async def test_report_requires_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
    hass_storage: dict[str, Any],
    command: str,
) -> None:
    """Test a non-admin user can't read or dismiss the report."""
    _store(hass_storage, _snapshot())
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_ws_client(hass, hass_read_only_access_token)

    await client.send_json_auto_id({"type": command})
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "unauthorized"


async def test_fix_flow_dismisses_report(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
    sensor: er.RegistryEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the fix flow of the issue shows the counts and dismisses the report."""
    _store(hass_storage, _snapshot(entities={"demo": {sensor.id: SENSOR}}))
    assert await async_setup_component(hass, DOMAIN, {})
    await _tick(hass, freezer, STARTUP_GRACE)
    client = await hass_client()

    resp = await client.post(
        "/api/repairs/issues/fix",
        json={"handler": DOMAIN, "issue_id": UPDATE_REPORT_ISSUE_ID},
    )
    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    assert data["step_id"] == "confirm"
    assert data["description_placeholders"]["entities"] == "1"

    resp = await client.post(f"/api/repairs/issues/fix/{data['flow_id']}")
    assert resp.status == HTTPStatus.OK
    assert (await resp.json())["type"] == "create_entry"

    assert not issue_registry.async_get_issue(DOMAIN, UPDATE_REPORT_ISSUE_ID)
    assert await _get_report(hass, hass_ws_client) is None
