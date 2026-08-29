"""Unit tests for the pure/self-contained helpers and mockable logic in coordinator.py.

Like ``config_flow.py``, this module uses relative imports and must be loaded
as a real package module. ``TrueNASCoordinator`` normally requires a running
Home Assistant (``__init__`` builds a real ``DataUpdateCoordinator``), which
``pytest-homeassistant-custom-component`` would be needed for -- unusable on
this repo's Windows dev machine (see the memory note on that incompatibility).
Instead, instance methods here are tested by constructing a bare instance via
``TrueNASCoordinator.__new__`` and setting only the attributes each method
under test actually touches, mirroring the Mock/AsyncMock approach already
used for ``TrueNASConfigFlow``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.truenas_ce import coordinator as coordinator_module
from homeassistant.components.truenas_ce.const import (
    BEHAVIOR_SKIP_DISABLED_CRONJOBS,
    CONF_BEHAVIORS,
    CONF_MONITORED_GROUPS,
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    MONITOR_GROUP_CLOUDSYNC,
    MONITOR_GROUP_CONTAINERS,
    MONITOR_GROUP_CRONJOBS,
    MONITOR_GROUP_DATASETS,
    MONITOR_GROUP_DIRECTORY_SERVICES,
    MONITOR_GROUP_REPLICATION,
    MONITOR_GROUP_RSYNC,
    MONITOR_GROUP_SNAPSHOTS,
    MONITOR_GROUP_UPS,
    MONITOR_GROUP_VMS,
)
from homeassistant.components.truenas_ce.coordinator import (
    TrueNASCoordinator,
    _as_str_keyed,
    _stat_name_similar,
    _unwrap_app_stats_message,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util


def _bare_coordinator() -> TrueNASCoordinator:
    """Build a TrueNASCoordinator without running its hass-dependent __init__."""
    coord = TrueNASCoordinator.__new__(TrueNASCoordinator)
    coord._app_stats_event_name = None
    coord._app_stats_sub_id = None
    coord.last_updatecheck_update = datetime(1970, 1, 1, tzinfo=UTC)
    return coord


# ---------------------------
#   _stat_name_similar
# ---------------------------
@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("cpu", "cpu", False),
        ("arc_size", "arcsize", True),
        ("cputemp", "cpu", True),
        ("cpu", "cputemp", True),
        (
            "memroy",  # codespell:ignore memroy -- deliberate typo under test
            "memory",
            True,
        ),
        ("load", "interface", False),
    ],
)
def test_stat_name_similar(a: str, b: str, expected: bool) -> None:
    """Two stat names are flagged similar when they share a common substem."""
    assert _stat_name_similar(a, b) == expected


# ---------------------------
#   _as_str_keyed
# ---------------------------
def test_as_str_keyed_stringifies_int_uids() -> None:
    """Int-typed uids (e.g. cronjob ids) are stringified for self.ds."""
    values = {"enabled": True}
    assert _as_str_keyed({5: values}) == {"5": values}


def test_as_str_keyed_leaves_str_uids_unchanged() -> None:
    """Already-str uids pass through unchanged."""
    values = {"enabled": True}
    assert _as_str_keyed({"already-str": values}) == {"already-str": values}


# ---------------------------
#   _is_group_monitored
# ---------------------------
def test_is_group_monitored_true_when_in_options() -> None:
    """A group present in the monitored-groups option is reported as monitored."""
    coord = _bare_coordinator()
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: [MONITOR_GROUP_VMS]}
    assert coord._is_group_monitored(MONITOR_GROUP_VMS) is True


def test_is_group_monitored_false_when_absent() -> None:
    """A group missing from the monitored-groups option is not monitored."""
    coord = _bare_coordinator()
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: []}
    assert coord._is_group_monitored(MONITOR_GROUP_VMS) is False


# ---------------------------
#   set_optimistic_running
# ---------------------------
def test_set_optimistic_running_sets_state_and_notifies() -> None:
    """Setting optimistic running state flips it to RUNNING and notifies listeners."""
    coord = _bare_coordinator()
    coord.ds = {"vm": {"1": {"state": "STOPPED"}}}
    coord.async_update_listeners = MagicMock()
    coord.set_optimistic_running("vm", "1")
    assert coord.ds["vm"]["1"]["state"] == "RUNNING"
    coord.async_update_listeners.assert_called_once()


def test_set_optimistic_running_noop_for_unknown_object_id() -> None:
    """An unknown object id leaves state untouched and does not notify."""
    coord = _bare_coordinator()
    coord.ds = {"vm": {"1": {"state": "STOPPED"}}}
    coord.async_update_listeners = MagicMock()
    coord.set_optimistic_running("vm", "does-not-exist")
    assert coord.ds["vm"]["1"]["state"] == "STOPPED"
    coord.async_update_listeners.assert_not_called()


def test_set_optimistic_running_normalizes_int_object_id() -> None:
    """A raw int object_id (e.g. rsynctask/replication/scrub ids) is looked up as str.

    Migrated endpoints are str-keyed end to end (see ``_as_str_keyed``), but
    callers pass the object's raw ``id`` field, which is still int-typed at
    the API level for several of them.
    """
    coord = _bare_coordinator()
    coord.ds = {"scrub": {"1": {"state": "PENDING"}}}
    coord.async_update_listeners = MagicMock()
    coord.set_optimistic_running("scrub", 1)
    assert coord.ds["scrub"]["1"]["state"] == "RUNNING"
    coord.async_update_listeners.assert_called_once()


# ---------------------------
#   async_run_task
# ---------------------------
async def test_async_run_task_marks_running_on_success() -> None:
    """A successful task query optimistically marks the object as RUNNING."""
    coord = _bare_coordinator()
    coord.ds = {"rsynctask": {"1": {"state": "STOPPED"}}}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value=42)
    coord.api.error = ""
    coord.async_update_listeners = MagicMock()
    await coord.async_run_task("rsynctask.run", "1", "rsynctask")
    assert coord.ds["rsynctask"]["1"]["state"] == "RUNNING"


async def test_async_run_task_raises_and_skips_optimistic_state_on_failure() -> None:
    """A failed task query raises HomeAssistantError and leaves state unchanged."""
    coord = _bare_coordinator()
    coord.ds = {"rsynctask": {"1": {"state": "STOPPED"}}}
    coord.host = "truenas.local"
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value=None)
    coord.api.error = "ERR_LOST_QUERY"
    coord.async_update_listeners = MagicMock()
    with pytest.raises(HomeAssistantError) as exc_info:
        await coord.async_run_task("rsynctask.run", "1", "rsynctask")
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "run_task_failed"
    assert exc_info.value.translation_placeholders == {
        "host": "truenas.local",
        "error": "ERR_LOST_QUERY",
    }
    assert coord.ds["rsynctask"]["1"]["state"] == "STOPPED"
    coord.async_update_listeners.assert_not_called()


# ---------------------------
#   _parse_version
# ---------------------------
def test_parse_version_extracts_major_minor() -> None:
    """The major/minor version numbers are parsed out of the version string."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {"version": "TrueNAS-SCALE-25.04.1"}}
    coord._parse_version()
    assert coord._version_major == 25
    assert coord._version_minor == 4


def test_parse_version_leaves_unset_on_no_match() -> None:
    """A version string that does not match the expected pattern leaves fields unset."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {"version": "not-a-version-string"}}
    coord._version_major = 0
    coord._version_minor = 0
    coord._parse_version()
    assert coord._version_major == 0
    assert coord._version_minor == 0


# ---------------------------
#   _detect_virtualization
# ---------------------------
def test_detect_virtualization_true_for_known_manufacturer() -> None:
    """A known hypervisor manufacturer string is detected as virtual."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {"system_manufacturer": "QEMU", "system_product": ""}}
    coord._detect_virtualization()
    assert coord._is_virtual is True


def test_detect_virtualization_true_for_known_product() -> None:
    """A known hypervisor product string is detected as virtual."""
    coord = _bare_coordinator()
    coord.ds = {
        "system_info": {"system_manufacturer": "", "system_product": "VirtualBox"}
    }
    coord._detect_virtualization()
    assert coord._is_virtual is True


def test_detect_virtualization_false_for_physical_hardware() -> None:
    """Physical hardware manufacturer/product strings are not detected as virtual."""
    coord = _bare_coordinator()
    coord.ds = {
        "system_info": {"system_manufacturer": "Dell Inc.", "system_product": "R730"}
    }
    coord._detect_virtualization()
    assert coord._is_virtual is False


# ---------------------------
#   _update_uptime
# ---------------------------
def test_update_uptime_sets_epoch_on_first_run() -> None:
    """A zero uptimeEpoch is populated from the current uptime on first run."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {"uptime_seconds": 3600, "uptimeEpoch": 0}}
    coord._update_uptime()
    assert coord.ds["system_info"]["uptimeEpoch"] > 0


def test_update_uptime_keeps_old_epoch_within_tolerance() -> None:
    """An epoch close enough to the freshly computed value is left unchanged."""
    coord = _bare_coordinator()
    now_epoch = int(dt_util.utcnow().timestamp())
    old_epoch = now_epoch - 3600 + 5  # within the 300s tolerance of a fresh reading
    coord.ds = {"system_info": {"uptime_seconds": 3600, "uptimeEpoch": old_epoch}}
    coord._update_uptime()
    assert coord.ds["system_info"]["uptimeEpoch"] == old_epoch


def test_update_uptime_replaces_stale_epoch_outside_tolerance() -> None:
    """An epoch drifted well past tolerance is replaced with a freshly computed one."""
    coord = _bare_coordinator()
    now_epoch = int(dt_util.utcnow().timestamp())
    old_epoch = now_epoch - 3600 - 600  # 600s drift, well beyond the 300s tolerance
    coord.ds = {"system_info": {"uptime_seconds": 3600, "uptimeEpoch": old_epoch}}
    coord._update_uptime()
    new_epoch = coord.ds["system_info"]["uptimeEpoch"]
    assert new_epoch != old_epoch
    # Replaced by a freshly computed epoch (now - uptime_seconds).
    assert abs(new_epoch - (now_epoch - 3600)) <= 5


def test_update_uptime_skips_when_uptime_not_positive() -> None:
    """A non-positive uptime_seconds leaves the existing uptimeEpoch untouched."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {"uptime_seconds": 0, "uptimeEpoch": 123}}
    coord._update_uptime()
    assert coord.ds["system_info"]["uptimeEpoch"] == 123


# ---------------------------
#   _systemstats_process / _store_stat_value / _store_stat_defaults
# ---------------------------
def test_systemstats_process_stores_matching_legend_values() -> None:
    """Each legend var's mean value is stored, missing means falling back to 0.0."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {}}
    graph = {
        "legend": ["shortterm", "midterm", "longterm"],
        "aggregations": {"mean": {"shortterm": 1.234, "midterm": 2.0}},
    }
    coord._systemstats_process(("shortterm", "midterm", "longterm"), graph, "load")
    assert coord.ds["system_info"]["load_shortterm"] == pytest.approx(1.23)
    assert coord.ds["system_info"]["load_midterm"] == pytest.approx(2.0)
    # "longterm" is in the legend but missing from the mean dict, so it falls
    # back to 0.0 rather than being skipped.
    assert coord.ds["system_info"]["load_longterm"] == pytest.approx(0.0)


def test_systemstats_process_falls_back_to_defaults_without_aggregations() -> None:
    """A graph with no aggregations stores default (0.0) values for each var."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {}}
    coord._systemstats_process("cpu", {}, "cpu")
    assert coord.ds["system_info"]["cpu_cpu"] == pytest.approx(0.0)


def test_systemstats_process_skips_legend_var_not_in_arr() -> None:
    """A legend var absent from the vars tuple is not stored."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {}}
    graph = {
        "legend": ["shortterm", "other"],
        "aggregations": {"mean": {"shortterm": 1.0, "other": 99.0}},
    }
    coord._systemstats_process(("shortterm",), graph, "load")
    assert coord.ds["system_info"]["load_shortterm"] == pytest.approx(1.0)
    assert "load_other" not in coord.ds["system_info"]


def test_store_stat_value_arcsize_uses_dedicated_key() -> None:
    """The arcsize/size stat is rounded and stored under its dedicated key."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {}}
    coord._store_stat_value("arcsize", "size", 12.345)
    assert coord.ds["system_info"]["cache_size-arc_value"] == pytest.approx(12.35)


def test_store_stat_value_cpu_uses_prefixed_key() -> None:
    """The cpu stat is stored under a "<type>_<var>" prefixed key."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {}}
    coord._store_stat_value("cpu", "cpu", 12.345)
    assert coord.ds["system_info"]["cpu_cpu"] == pytest.approx(12.35)


def test_store_stat_value_memory_only_stores_available() -> None:
    """Only the memory "available" var is stored; other memory vars are ignored."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {}}
    coord._store_stat_value("memory", "available", 100.0)
    assert coord.ds["system_info"]["memory-free_value"] == 100
    coord._store_stat_value("memory", "used", 50.0)
    assert "memory-used" not in coord.ds["system_info"]


def test_store_stat_value_unknown_type_stores_raw_key() -> None:
    """An unrecognized stat type falls back to storing under the raw var name."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {}}
    coord._store_stat_value("diskstats", "reads", 12.345)
    assert coord.ds["system_info"]["reads"] == pytest.approx(12.35)


# ---------------------------
#   get_alerts
# ---------------------------
# The dismissed-filtering/level-counting/disk_issues-heuristic derivation
# these tests used to exercise directly now lives in and is tested by
# aiotruenas's own TrueNASState.get_alerts(). get_alerts() just delegates and
# assigns the result, so this only needs to lock in that plumbing.
async def test_get_alerts_delegates_to_state() -> None:
    """get_alerts assigns TrueNASState.get_alerts()'s result verbatim."""
    coord = _bare_coordinator()
    coord.ds = {"alerts": {}}
    coord.state = MagicMock()
    coord.state.get_alerts = AsyncMock(
        return_value={
            "count": 1,
            "messages": ["Pool full"],
            "critical": 1,
            "warning": 0,
            "info": 0,
            "disk_issues": True,
            "uuids": ["u1"],
        }
    )
    await coord.get_alerts()
    assert coord.ds["alerts"]["count"] == 1
    assert coord.ds["alerts"]["uuids"] == ["u1"]


# ---------------------------
#   get_smb
# ---------------------------
# The list-vs-dict response-shape handling these tests used to exercise
# directly now lives in and is tested by aiotruenas's own
# TrueNASState.get_smb(). get_smb() just delegates and merges "connections"
# into system_info, so this only needs to lock in that plumbing.
async def test_get_smb_merges_connections_into_system_info() -> None:
    """get_smb copies TrueNASState.get_smb()'s "connections" into system_info."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {}}
    coord.state = MagicMock()
    coord.state.get_smb = AsyncMock(return_value={"connections": 3})
    await coord.get_smb()
    assert coord.ds["system_info"]["smb_connections"] == 3


async def test_get_smb_leaves_system_info_untouched_without_connections_key() -> None:
    """A malformed/failed state response (no "connections" key) is a no-op."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {"smb_connections": 3}}
    coord.state = MagicMock()
    coord.state.get_smb = AsyncMock(return_value={})
    await coord.get_smb()
    assert coord.ds["system_info"]["smb_connections"] == 3


# ---------------------------
#   get_updatecheck
# ---------------------------
# The update.status parsing/malformed-response handling these tests used to
# exercise directly now lives in and is tested by aiotruenas's own
# TrueNASState.get_update(). get_updatecheck just merges the result into
# ds["system_info"], so this only needs to lock in that plumbing.
async def test_get_updatecheck_no_update_falls_back_to_running_version() -> None:
    """No pending update: the resting "up-to-date" version is replaced with the running one."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {"version": "25.04.1"}}
    coord.state = MagicMock()
    coord.state.get_update = AsyncMock(
        return_value={
            "update_available": False,
            "update_state": "IDLE",
            "update_version": "up-to-date",
            "update_date": None,
            "update_profile": None,
            "update_train": None,
            "update_filename": None,
        }
    )
    await coord.get_updatecheck()
    info = coord.ds["system_info"]
    assert info["update_available"] is False
    assert info["update_version"] == "25.04.1"


async def test_get_updatecheck_pending_update_keeps_new_version() -> None:
    """A pending update's own version is not overridden by the running version."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {"version": "25.04.1"}}
    coord.state = MagicMock()
    coord.state.get_update = AsyncMock(
        return_value={
            "update_available": True,
            "update_state": "AVAILABLE",
            "update_version": "25.10.0",
            "update_date": None,
            "update_profile": None,
            "update_train": None,
            "update_filename": None,
        }
    )
    await coord.get_updatecheck()
    info = coord.ds["system_info"]
    assert info["update_available"] is True
    assert info["update_version"] == "25.10.0"


async def test_start_app_stats_stops_when_containers_not_monitored() -> None:
    """Stats subscription is stopped and cleared when containers are unmonitored."""
    coord = _bare_coordinator()
    coord.ds = {
        "app": {"test-app": {}},
        "app_stats": {"old-app": {"app_name": "old-app"}},
    }
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.subscribe_events = AsyncMock(return_value=("sub-new", MagicMock()))
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: []}
    coord._app_stats_sub_id = "sub-old"
    coord._app_stats_event_name = 'app.stats:{"interval": 5}'

    with patch.object(coord, "stop_app_stats", new=AsyncMock()) as stop_mock:
        await coord.start_app_stats()

    stop_mock.assert_awaited_once_with(force=True)
    assert coord.ds["app_stats"] == {}


async def test_start_app_stats_clears_stats_when_never_subscribed() -> None:
    """Containers unmonitored and never subscribed: clear stats, no stop."""
    coord = _bare_coordinator()
    coord.ds = {
        "app": {"test-app": {}},
        "app_stats": {"old-app": {"app_name": "old-app"}},
    }
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.subscribe_events = AsyncMock(return_value=("sub-new", MagicMock()))
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: []}
    coord._app_stats_sub_id = None
    coord._app_stats_event_name = None

    with patch.object(coord, "stop_app_stats", new=AsyncMock()) as stop_mock:
        await coord.start_app_stats()

    stop_mock.assert_not_awaited()
    assert coord.ds["app_stats"] == {}


async def test_start_app_stats_defaults_when_config_entry_missing() -> None:
    """start_app_stats should treat groups as monitored when config_entry is None."""
    coord = _bare_coordinator()
    coord.ds = {
        "app": {"test-app": {"name": "test-app"}},
        "app_stats": {},
    }
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.subscribe_events = AsyncMock(return_value=("sub-new", MagicMock()))
    coord.config_entry = None
    coord._app_stats_sub_id = None
    coord._app_stats_event_name = 'app.stats:{"interval": 5}'

    with patch.object(
        coord, "_is_group_monitored", wraps=coord._is_group_monitored
    ) as monitored_mock:
        await coord.start_app_stats()

    monitored_mock.assert_called()
    coord.api.subscribe_events.assert_awaited_once()


async def test_start_app_stats_defaults_when_monitored_groups_missing() -> None:
    """Treat groups as monitored when CONF_MONITORED_GROUPS is absent."""
    coord = _bare_coordinator()
    coord.ds = {
        "app": {"test-app": {"name": "test-app"}},
        "app_stats": {},
    }
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.subscribe_events = AsyncMock(return_value=("sub-new", MagicMock()))
    coord.config_entry = MagicMock()
    coord.config_entry.options = {}
    coord._app_stats_sub_id = None
    coord._app_stats_event_name = 'app.stats:{"interval": 5}'

    with patch.object(
        coord, "_is_group_monitored", wraps=coord._is_group_monitored
    ) as monitored_mock:
        await coord.start_app_stats()

    monitored_mock.assert_called()
    coord.api.subscribe_events.assert_awaited_once()


async def test_start_app_stats_noops_when_api_not_connected() -> None:
    """A disconnected API skips subscribing and leaves existing stats untouched."""
    coord = _bare_coordinator()
    coord.ds = {
        "app": {"test-app": {}},
        "app_stats": {"existing-app": {"app_name": "existing-app"}},
    }
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=False)
    coord.api.subscribe_events = AsyncMock()
    coord.config_entry = MagicMock()
    coord.config_entry.options = {
        CONF_MONITORED_GROUPS: ["app", MONITOR_GROUP_CONTAINERS]
    }
    coord._app_stats_sub_id = None
    coord._app_stats_event_name = 'app.stats:{"interval": 5}'

    with patch.object(coord, "stop_app_stats", new=AsyncMock()) as stop_mock:
        await coord.start_app_stats()

    coord.api.subscribe_events.assert_not_called()
    stop_mock.assert_not_awaited()
    assert coord.ds["app_stats"] == {
        "existing-app": {"app_name": "existing-app"},
    }


async def test_start_app_stats_keeps_existing_sub_when_no_apps() -> None:
    """With no apps and same event name, start_app_stats keeps the existing sub."""
    coord = _bare_coordinator()
    coord.ds = {"app": {}, "app_stats": {"existing-app": {"app_name": "existing-app"}}}

    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.subscribe_events = AsyncMock(return_value=("sub-new", MagicMock()))
    coord.api.is_subscribed = AsyncMock(return_value=True)

    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: [MONITOR_GROUP_CONTAINERS]}

    coord._app_stats_sub_id = "sub-old"
    coord._app_stats_event_name = 'app.stats:{"interval": 60}'

    await coord.start_app_stats()

    coord.api.subscribe_events.assert_not_awaited()
    assert coord._app_stats_sub_id == "sub-old"
    assert coord._app_stats_event_name == 'app.stats:{"interval": 60}'


async def test_get_app_stats_clears_when_containers_not_monitored() -> None:
    """get_app_stats clears stale app stats once containers are unmonitored."""
    coord = _bare_coordinator()
    coord.ds = {"app_stats": {"stale-app": {"cpu": 1}}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: []}
    coord.api = MagicMock()
    coord.stop_app_stats = AsyncMock()
    coord._app_stats_sub_id = "sub-1"

    await coord.get_app_stats()

    coord.stop_app_stats.assert_awaited_once_with(force=True)
    assert coord.ds["app_stats"] == {}


async def test_get_app_stats_does_nothing_when_disconnected_mid_call() -> None:
    """A disconnected API leaves the stats dict and subscription id unchanged."""
    coord = _bare_coordinator()
    coord.ds = {
        "app": {"test-app": {"name": "test-app"}},
        "app_stats": {"test-app": {"cpu": 1, "memory": 2}},
    }
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=False)
    coord.api.get_subscription_events = AsyncMock()
    coord.api.is_subscribed = AsyncMock()
    coord._app_stats_sub_id = "existing-sub-id"

    original_ds = coord.ds.copy()
    original_sub_id = coord._app_stats_sub_id

    await coord.get_app_stats()

    coord.api.get_subscription_events.assert_not_called()
    assert coord.ds == original_ds
    assert coord._app_stats_sub_id == original_sub_id


async def test_get_app_stats_does_nothing_when_no_apps() -> None:
    """No apps: get_app_stats is a no-op."""
    coord = _bare_coordinator()
    coord.ds = {
        "app": {},
        "app_stats": {"existing-app": {"app_name": "existing-app"}},
    }
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.get_subscription_events = AsyncMock()
    coord.api.is_subscribed = AsyncMock(return_value=True)
    coord._app_stats_sub_id = "sub-1"

    await coord.get_app_stats()

    coord.api.get_subscription_events.assert_not_called()
    assert coord.ds["app_stats"] == {"existing-app": {"app_name": "existing-app"}}


async def test_get_app_stats_re_subscribes_when_sub_id_missing() -> None:
    """A missing subscription id triggers a call to start_app_stats to resubscribe."""
    coord = _bare_coordinator()
    coord.ds = {
        "app": {"test-app": {"name": "test-app"}},
        "app_stats": {},
    }
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.get_subscription_events = AsyncMock(return_value=[])
    coord.api.is_subscribed = AsyncMock(return_value=False)
    coord._app_stats_sub_id = None

    with patch.object(coord, "start_app_stats", new_callable=AsyncMock) as start_mock:
        await coord.get_app_stats()

    start_mock.assert_awaited_once()


async def test_get_app_stats_re_subscribes_when_existing_sub_not_active() -> None:
    """If sub_id exists but api.is_subscribed is False, clear and resubscribe."""
    coord = _bare_coordinator()
    coord.ds = {
        "app": {"test-app": {"name": "test-app"}},
        "app_stats": {},
    }
    original_sub_id = "sub-1"
    coord._app_stats_sub_id = original_sub_id

    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.get_subscription_events = AsyncMock(return_value=[])
    coord.api.is_subscribed = AsyncMock(return_value=False)

    with patch.object(coord, "start_app_stats", new_callable=AsyncMock) as start_mock:
        await coord.get_app_stats()

    start_mock.assert_awaited_once()


async def test_get_app_stats_skips_malformed_app_name() -> None:
    """Events with a non-string or empty app_name are skipped, valid ones are kept."""
    coord = _bare_coordinator()
    coord.ds = {
        "app": {"test-app": {"name": "test-app"}},
        "app_stats": {},
    }
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.get_subscription_events = AsyncMock(
        return_value=[
            {"fields": [{"app_name": 123}]},
            {"fields": [{"app_name": "", "cpu_usage": 2.0}]},
            {"fields": [{"app_name": "test-app", "cpu_usage": 1.0}]},
        ]
    )
    coord._app_stats_sub_id = "sub-1"
    coord.api.is_subscribed = AsyncMock(return_value=True)

    await coord.get_app_stats()

    assert "test-app" in coord.ds["app_stats"]
    assert 123 not in coord.ds["app_stats"]
    assert "" not in coord.ds["app_stats"]


# ---------------------------
#   start_app_stats / get_app_stats / stop_app_stats
# ---------------------------
async def test_start_app_stats_subscribes_once() -> None:
    """start_app_stats subscribes and records the returned subscription id."""
    coord = _bare_coordinator()
    coord.ds = {"app": {"test-app": {}}}
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.subscribe_events = AsyncMock(return_value=("sub-1", MagicMock()))
    coord.config_entry = MagicMock()
    coord.config_entry.options = {}
    coord._app_stats_sub_id = None

    await coord.start_app_stats()

    coord.api.subscribe_events.assert_awaited_once()
    assert coord._app_stats_sub_id == "sub-1"


async def test_start_app_stats_clears_stale_subscription() -> None:
    """A stale subscription is unsubscribed before a new one is established."""
    coord = _bare_coordinator()
    coord.ds = {"app": {"test-app": {}}}
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.subscribe_events = AsyncMock(return_value=("sub-new", MagicMock()))
    coord.api.unsubscribe_events = AsyncMock()
    coord.config_entry = MagicMock()
    coord.config_entry.options = {}
    coord._app_stats_sub_id = "sub-old"
    coord._app_stats_event_name = 'app.stats:{"interval": 5}'

    await coord.start_app_stats()

    coord.api.unsubscribe_events.assert_awaited_once_with("sub-old")
    coord.api.subscribe_events.assert_awaited_once()
    assert coord._app_stats_sub_id == "sub-new"


async def test_start_app_stats_handles_subscribe_failure() -> None:
    """A subscribe_events exception is swallowed, leaving the subscription id unset."""
    coord = _bare_coordinator()
    coord.ds = {"app": {"test-app": {}}}
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.subscribe_events = AsyncMock(side_effect=Exception("subscribe failed"))
    coord.config_entry = MagicMock()
    coord.config_entry.options = {}
    coord._app_stats_sub_id = None

    await coord.start_app_stats()

    assert coord._app_stats_sub_id is None


async def test_get_app_stats_processes_and_updates_state() -> None:
    """A subscription event's fields are normalized into per-app stats state."""
    coord = _bare_coordinator()
    coord.ds = {
        "app": {"test-app": {"name": "test-app"}},
        "app_stats": {},
    }
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.get_subscription_events = AsyncMock(
        return_value=[
            {
                "fields": [
                    {
                        "app_name": "test-app",
                        "cpu_usage": 12.5,
                        "memory": 1024000,
                        "blkio": {"read": 5000, "write": 2000},
                        "networks": [
                            {
                                "interface_name": "eth0",
                                "rx_bytes": 1000,
                                "tx_bytes": 500,
                            }
                        ],
                    }
                ]
            }
        ]
    )
    coord._app_stats_sub_id = "sub-1"
    coord.api.is_subscribed = AsyncMock(return_value=True)

    await coord.get_app_stats()

    assert coord.ds["app_stats"]["test-app"]["app_name"] == "test-app"
    assert coord.ds["app_stats"]["test-app"]["cpu_usage"] == pytest.approx(12.5)
    assert coord.ds["app_stats"]["test-app"]["memory"] == 1024000
    assert coord.ds["app_stats"]["test-app"]["blkio_read"] == 5000
    assert coord.ds["app_stats"]["test-app"]["blkio_write"] == 2000
    assert coord.ds["app_stats"]["test-app"]["networks"] == [
        {"interface_name": "eth0", "rx_bytes": 1000, "tx_bytes": 500}
    ]


async def test_get_app_stats_removes_missing_apps() -> None:
    """Stats for apps no longer in coord.ds["app"] are dropped."""
    coord = _bare_coordinator()
    coord.ds = {
        "app": {
            "test-app": {"name": "test-app"},
        },
        "app_stats": {
            "test-app": {"app_name": "test-app"},
            "old-app": {"app_name": "old-app"},
        },
    }
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.get_subscription_events = AsyncMock(return_value=[])
    coord._app_stats_sub_id = "sub-1"
    coord.api.is_subscribed = AsyncMock(return_value=True)

    await coord.get_app_stats()

    assert "test-app" in coord.ds["app_stats"]
    assert "old-app" not in coord.ds["app_stats"]


async def test_get_app_stats_skips_malformed_fields() -> None:
    """Malformed fields entries are skipped while well-formed ones are processed."""
    coord = _bare_coordinator()
    coord.ds = {
        "app": {"test-app": {"name": "test-app"}},
        "app_stats": {},
    }
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.get_subscription_events = AsyncMock(
        return_value=[
            {"fields": "not-a-list"},
            {"fields": [{"not_an_app": 1}]},
            {"fields": [{"app_name": "test-app", "cpu_usage": 1.0}]},
        ]
    )
    coord._app_stats_sub_id = "sub-1"
    coord.api.is_subscribed = AsyncMock(return_value=True)

    await coord.get_app_stats()

    assert "test-app" in coord.ds["app_stats"]
    assert coord.ds["app_stats"]["test-app"]["cpu_usage"] == pytest.approx(1.0)


async def test_stop_app_stats_unsubscribes_events() -> None:
    """stop_app_stats unsubscribes and clears the tracked subscription state."""
    coord = _bare_coordinator()
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.unsubscribe_events = AsyncMock()
    coord._app_stats_sub_id = "sub-1"

    await coord.stop_app_stats()

    coord.api.unsubscribe_events.assert_awaited_once_with("sub-1")
    assert coord._app_stats_sub_id is None
    assert coord._app_stats_event_name is None


async def test_stop_app_stats_default_clears_even_when_disconnected() -> None:
    """A disconnected API skips the unsubscribe call but still clears local state."""
    coord = _bare_coordinator()
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=False)
    coord.api.unsubscribe_events = AsyncMock()
    coord._app_stats_sub_id = "sub-1"
    coord._app_stats_event_name = 'app.stats:{"interval": 5}'

    await coord.stop_app_stats()

    coord.api.unsubscribe_events.assert_not_awaited()
    assert coord._app_stats_sub_id is None
    assert coord._app_stats_event_name is None


async def test_get_app_stats_unwraps_collection_update_envelope() -> None:
    """A collection_update-wrapped event's params.fields are still processed."""
    coord = _bare_coordinator()
    coord.ds = {
        "app": {"test-app": {"name": "test-app"}},
        "app_stats": {},
    }
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.get_subscription_events = AsyncMock(
        return_value=[
            {
                "method": "collection_update",
                "params": {
                    "fields": [
                        {
                            "app_name": "test-app",
                            "cpu_usage": 12.5,
                            "memory": 1024000,
                            "blkio": {"read": 5000, "write": 2000},
                            "networks": [
                                {
                                    "interface_name": "eth0",
                                    "rx_bytes": 1000,
                                    "tx_bytes": 500,
                                }
                            ],
                        }
                    ]
                },
            }
        ]
    )
    coord._app_stats_sub_id = "sub-1"
    coord.api.is_subscribed = AsyncMock(return_value=True)

    await coord.get_app_stats()

    assert coord.ds["app_stats"]["test-app"]["app_name"] == "test-app"
    assert coord.ds["app_stats"]["test-app"]["cpu_usage"] == pytest.approx(12.5)
    assert coord.ds["app_stats"]["test-app"]["memory"] == 1024000
    assert coord.ds["app_stats"]["test-app"]["blkio_read"] == 5000
    assert coord.ds["app_stats"]["test-app"]["blkio_write"] == 2000
    assert coord.ds["app_stats"]["test-app"]["networks"] == [
        {"interface_name": "eth0", "rx_bytes": 1000, "tx_bytes": 500}
    ]


async def test_get_app_stats_handles_missing_blkio_and_networks() -> None:
    """Malformed blkio/networks fields fall back to None/empty-list defaults."""
    coord = _bare_coordinator()
    coord.ds = {
        "app": {"test-app": {"name": "test-app"}},
        "app_stats": {},
    }
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.get_subscription_events = AsyncMock(
        return_value=[
            {
                "fields": [
                    {
                        "app_name": "test-app",
                        "cpu_usage": 1.0,
                        "memory": 1024,
                        "blkio": "not-a-dict",
                        "networks": "not-a-list",
                    }
                ]
            }
        ]
    )
    coord._app_stats_sub_id = "sub-1"
    coord.api.is_subscribed = AsyncMock(return_value=True)

    await coord.get_app_stats()

    assert coord.ds["app_stats"]["test-app"]["blkio_read"] is None
    assert coord.ds["app_stats"]["test-app"]["blkio_write"] is None
    assert coord.ds["app_stats"]["test-app"]["networks"] == []


async def test_get_app_stats_handles_malformed_networks_list() -> None:
    """Ensure _upsert_app_stats_entry keeps only valid network dicts."""
    coord = _bare_coordinator()
    coord.ds = {
        "app": {"test-app": {"name": "test-app"}},
        "app_stats": {},
    }
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.get_subscription_events = AsyncMock(
        return_value=[
            {
                "fields": [
                    {
                        "app_name": "test-app",
                        "cpu_usage": 5.0,
                        "memory": 2048,
                        "networks": [
                            "bad",
                            {"interface_name": None, "rx_bytes": 10, "tx_bytes": 20},
                            {},
                            {
                                "interface_name": "eth0",
                                "rx_bytes": 1000,
                                "tx_bytes": 500,
                            },
                            {
                                "interface_name": "eth1",
                                "rx_bytes": 2000,
                                "tx_bytes": 1500,
                            },
                        ],
                    }
                ]
            }
        ]
    )
    coord._app_stats_sub_id = "sub-1"
    coord.api.is_subscribed = AsyncMock(return_value=True)

    await coord.get_app_stats()

    networks = coord.ds["app_stats"]["test-app"]["networks"]
    assert networks == [
        {"interface_name": "eth0", "rx_bytes": 1000, "tx_bytes": 500},
        {"interface_name": "eth1", "rx_bytes": 2000, "tx_bytes": 1500},
    ]


async def test_get_app_stats_ignores_non_dict_app_entries() -> None:
    """Ensure _upsert_app_stats_entry ignores non-dict app objects in messages."""
    coord = _bare_coordinator()
    coord.ds = {
        "app": {"test-app": {"name": "test-app"}},
        "app_stats": {},
    }
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.get_subscription_events = AsyncMock(
        return_value=[
            {"fields": ["not-a-dict", 42, None]},
        ]
    )
    coord._app_stats_sub_id = "sub-1"
    coord.api.is_subscribed = AsyncMock(return_value=True)

    await coord.get_app_stats()

    assert coord.ds["app_stats"] == {}


async def test_get_app_stats_normalizes_invalid_app_stats_to_none() -> None:
    """Invalid cpu_usage/memory/blkio_read values should be normalized to None."""
    coord = _bare_coordinator()
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.get_subscription_events = AsyncMock(
        return_value=[
            {
                "fields": [
                    {
                        "app_name": "test-app",
                        "cpu_usage": "bad",
                        "memory": {},
                        "blkio": {"read": "x"},
                        "networks": [],
                    }
                ]
            }
        ]
    )
    coord._app_stats_sub_id = "sub-1"
    coord.api.is_subscribed = AsyncMock(return_value=True)
    coord.ds = {"app": {"test-app": {"name": "test-app"}}, "app_stats": {}}

    await coord.get_app_stats()

    assert coord.ds["app_stats"]["test-app"]["cpu_usage"] is None
    assert coord.ds["app_stats"]["test-app"]["memory"] is None
    assert coord.ds["app_stats"]["test-app"]["blkio_read"] is None


def test_unwrap_app_stats_message_accepts_collection_update() -> None:
    """A collection_update-wrapped message's params.fields are unwrapped."""
    msg = {"method": "collection_update", "params": {"fields": [{"app_name": "x"}]}}
    assert _unwrap_app_stats_message(msg) == {"fields": [{"app_name": "x"}]}


def test_unwrap_app_stats_message_accepts_top_level_fields() -> None:
    """A message with top-level fields is returned unchanged."""
    msg = {"fields": [{"app_name": "x"}]}
    assert _unwrap_app_stats_message(msg) == msg


def test_unwrap_app_stats_message_rejects_missing_fields() -> None:
    """Messages missing a usable fields key all unwrap to None."""
    assert (
        _unwrap_app_stats_message({"method": "collection_update", "params": {}}) is None
    )
    assert (
        _unwrap_app_stats_message(
            {"method": "collection_update", "params": {"other": 1}}
        )
        is None
    )
    assert _unwrap_app_stats_message({"method": "collection_update"}) is None
    assert _unwrap_app_stats_message({"other": "data"}) is None


def test_unwrap_app_stats_message_rejects_non_dict_params() -> None:
    """A non-dict params value unwraps to None instead of raising."""
    assert (
        _unwrap_app_stats_message({"method": "collection_update", "params": "bad"})
        is None
    )


async def test_start_app_stats_falls_back_on_invalid_poll_interval() -> None:
    """A non-numeric poll interval option falls back to the default interval."""
    coord = _bare_coordinator()
    coord.ds = {"app": {"test-app": {}}}
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.subscribe_events = AsyncMock(return_value=("sub-new", MagicMock()))
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_POLL_INTERVAL: "not-a-number"}
    coord._app_stats_sub_id = "sub-old"
    coord._app_stats_event_name = 'app.stats:{"interval": 5}'

    await coord.start_app_stats()

    assert (
        coord._app_stats_event_name
        == f'app.stats:{{"interval": {DEFAULT_POLL_INTERVAL}}}'
    )
    coord.api.subscribe_events.assert_awaited_once()


# ---------------------------
#   connected
# ---------------------------
# Note: TrueNASCoordinator.__init__ itself is not unit-tested here -- HA's
# DataUpdateCoordinator.__init__ calls frame.report_usage(), which requires
# hass's frame helper to have been set up by a running Home Assistant core
# (unavailable via pytest-homeassistant-custom-component on this Windows dev
# machine). It is exercised by CI's hass-fixture-based integration tests.
def test_connected_delegates_to_api() -> None:
    """coord.connected() delegates directly to the API's connected() call."""
    coord = _bare_coordinator()
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    assert coord.connected() is True
    coord.api.connected.assert_called_once()


# ---------------------------
#   _async_ensure_connected
# ---------------------------
async def test_async_ensure_connected_noop_when_already_connected() -> None:
    """An already-connected API is not asked to connect again."""
    coord = _bare_coordinator()
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.connect = AsyncMock()
    await coord._async_ensure_connected()
    coord.api.connect.assert_not_awaited()


async def test_async_ensure_connected_raises_update_failed_on_exception() -> None:
    """A connect() exception is translated into UpdateFailed."""
    coord = _bare_coordinator()
    coord.host = "truenas.local"
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=False)
    coord.api.connect = AsyncMock(side_effect=Exception("boom"))
    with pytest.raises(coordinator_module.UpdateFailed):
        await coord._async_ensure_connected()


async def test_async_ensure_connected_raises_update_failed_on_invalid_key() -> None:
    """An ERR_INVALID_KEY connect failure is translated into UpdateFailed.

    Bronze scope has no reauth flow to hand off to, so this degrades to the
    same UpdateFailed/entity-unavailable path as any other connection failure
    instead of ConfigEntryAuthFailed (see coordinator._async_ensure_connected).
    """
    coord = _bare_coordinator()
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=False)
    coord.api.connect = AsyncMock(return_value=False)
    coord.api.error = "ERR_INVALID_KEY"
    coord.host = "truenas.local"
    with (
        patch.object(coordinator_module, "ERR_INVALID_KEY", "ERR_INVALID_KEY"),
        pytest.raises(coordinator_module.UpdateFailed),
    ):
        await coord._async_ensure_connected()


async def test_async_ensure_connected_raises_update_failed_on_other_error() -> None:
    """A non-auth connect failure is translated into UpdateFailed."""
    coord = _bare_coordinator()
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=False)
    coord.api.connect = AsyncMock(return_value=False)
    coord.api.error = "ERR_LOST_QUERY"
    coord.host = "truenas.local"
    with pytest.raises(coordinator_module.UpdateFailed):
        await coord._async_ensure_connected()


async def test_async_ensure_connected_succeeds() -> None:
    """A successful connect() call completes without raising."""
    coord = _bare_coordinator()
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=False)
    coord.api.connect = AsyncMock(return_value=True)
    await coord._async_ensure_connected()  # must not raise


# ---------------------------
#   _async_update_data
# ---------------------------
def _stub_all_jobs(coord: TrueNASCoordinator) -> None:
    """Patch every job invoked by ``_async_update_data`` with a no-op AsyncMock."""
    for name in (
        "get_systeminfo",
        "get_systemstats",
        "get_disk",
        "get_dataset",
        "get_directoryservices",
        "get_cloudsync",
        "get_replication",
        "get_rsync",
        "get_snapshottask",
        "get_scrub",
        "get_app",
        "get_app_stats",
        "get_alerts",
        "get_certificates",
        "get_arc",
        "get_smb",
        "get_ups",
        "get_pool",
        "get_updatecheck",
    ):
        setattr(coord, name, AsyncMock())


async def test_async_update_data_runs_jobs_when_connected() -> None:
    """All get_* jobs run and the coordinator's ds dict is returned when connected."""
    coord = _bare_coordinator()
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord._async_ensure_connected = AsyncMock()
    coord.last_updatecheck_update = datetime(1970, 1, 1, tzinfo=UTC)
    _stub_all_jobs(coord)
    coord.ds = {"foo": "bar", "system_info": {"hostname": "truenas"}}

    result = await coord._async_update_data()

    coord.get_systeminfo.assert_awaited_once()
    coord.get_pool.assert_awaited_once()
    coord.get_updatecheck.assert_awaited_once()
    assert result is coord.ds


async def test_async_update_data_skips_jobs_when_disconnected() -> None:
    """A still-disconnected API raises UpdateFailed and skips running any jobs."""
    coord = _bare_coordinator()
    coord.host = "truenas.local"
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=False)
    coord._async_ensure_connected = AsyncMock()
    _stub_all_jobs(coord)

    with pytest.raises(coordinator_module.UpdateFailed):
        await coord._async_update_data()

    coord.get_systeminfo.assert_not_awaited()


async def test_async_update_data_swallows_job_exceptions() -> None:
    """A single job raising an exception does not abort the overall update."""
    coord = _bare_coordinator()
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord._async_ensure_connected = AsyncMock()
    coord.last_updatecheck_update = dt_util.utcnow()
    _stub_all_jobs(coord)
    coord.get_disk = AsyncMock(side_effect=Exception("boom"))
    coord.ds = {"system_info": {"hostname": "truenas"}}

    result = await coord._async_update_data()  # must not raise

    assert result is coord.ds


async def test_async_update_data_raises_when_system_info_missing() -> None:
    """A first refresh missing system.info must not be reported as successful."""
    coord = _bare_coordinator()
    coord.host = "truenas.local"
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord._async_ensure_connected = AsyncMock()
    _stub_all_jobs(coord)
    coord.ds = {"system_info": {}}

    with pytest.raises(coordinator_module.UpdateFailed):
        await coord._async_update_data()

    coord.get_systeminfo.assert_awaited_once()
    coord.get_pool.assert_not_awaited()


# ---------------------------
#   get_systeminfo / _handle_update_job / _query_interfaces
# ---------------------------
async def test_get_systeminfo_parses_valid_response_and_runs_pipeline() -> None:
    """A valid system-info response is parsed and the update-job pipeline runs."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {}, "interface": {}}
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.query = AsyncMock(
        return_value={
            "version": "TrueNAS-SCALE-25.04.1",
            "hostname": "nas1",
            "uptime_seconds": 100,
            "physmem": 1000,
        }
    )
    coord._handle_update_job = AsyncMock()

    await coord.get_systeminfo()

    assert coord.ds["system_info"]["hostname"] == "nas1"
    assert coord.ds["system_info"]["update_version"] == "TrueNAS-SCALE-25.04.1"
    assert coord._version_major == 25
    coord._handle_update_job.assert_awaited_once()


async def test_get_systeminfo_skips_parse_on_invalid_response() -> None:
    """A None system-info response skips parsing but still runs the update job."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {}, "interface": {}}
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.query = AsyncMock(return_value=None)
    coord._handle_update_job = AsyncMock()

    await coord.get_systeminfo()

    coord._handle_update_job.assert_awaited_once()


async def test_get_systeminfo_returns_early_when_disconnected_after_parse() -> None:
    """Disconnection after parsing returns early before the update-job pipeline."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {}, "interface": {}}
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=False)
    coord.api.query = AsyncMock(return_value={"version": "25.04.1"})
    coord._handle_update_job = AsyncMock()

    await coord.get_systeminfo()

    coord._handle_update_job.assert_not_awaited()


async def test_get_systeminfo_returns_early_disconnected_after_update_job() -> None:
    """Disconnection right after the update job skips further version parsing."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {}, "interface": {}}
    coord.api = MagicMock()
    # Connected for the pre-update-job check, disconnected right after.
    coord.api.connected = MagicMock(side_effect=[True, False])
    coord.api.query = AsyncMock(return_value={"version": "25.04.1"})
    coord._handle_update_job = AsyncMock()
    coord._parse_version = MagicMock()

    await coord.get_systeminfo()

    coord._handle_update_job.assert_awaited_once()
    coord._parse_version.assert_not_called()


async def test_handle_update_job_noop_without_jobid() -> None:
    """A zero update_jobid means no job status query is made."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {"update_jobid": 0}}
    coord.api = MagicMock()
    coord.api.query = AsyncMock()
    await coord._handle_update_job()
    coord.api.query.assert_not_awaited()


async def test_handle_update_job_keeps_progress_while_running() -> None:
    """A RUNNING update job's progress percentage and state are stored."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {"update_jobid": 5, "update_available": True}}
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.query = AsyncMock(
        return_value={"progress": {"percent": 42}, "state": "RUNNING"}
    )
    await coord._handle_update_job()
    assert coord.ds["system_info"]["update_progress"] == 42
    assert coord.ds["system_info"]["update_state"] == "RUNNING"


async def test_handle_update_job_resets_when_finished() -> None:
    """A finished (SUCCESS) update job resets jobid/progress/state to idle defaults."""
    coord = _bare_coordinator()
    coord.ds = {
        "system_info": {
            "update_jobid": 5,
            "update_available": False,
            "version": "25.04.1",
        }
    }
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.query = AsyncMock(
        return_value={"progress": {"percent": 100}, "state": "SUCCESS"}
    )
    await coord._handle_update_job()
    assert coord.ds["system_info"]["update_progress"] == 0
    assert coord.ds["system_info"]["update_jobid"] == 0
    assert coord.ds["system_info"]["update_state"] == "unknown"


async def test_handle_update_job_returns_early_when_disconnected() -> None:
    """A disconnected API leaves the existing update_jobid untouched."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {"update_jobid": 5}}
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=False)
    coord.api.query = AsyncMock(return_value=None)
    await coord._handle_update_job()
    assert coord.ds["system_info"]["update_jobid"] == 5


async def test_query_interfaces_derives_link_up() -> None:
    """Each interface's link_up flag is derived from its reported link state."""
    coord = _bare_coordinator()
    coord.ds = {"interface": {}}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(
        return_value=[
            {"id": "eth0", "name": "eth0", "state": {"link_state": "LINK_STATE_UP"}},
            {"id": "eth1", "name": "eth1", "state": {"link_state": "LINK_STATE_DOWN"}},
        ]
    )
    await coord._query_interfaces()
    assert coord.ds["interface"]["eth0"]["link_up"] is True
    assert coord.ds["interface"]["eth1"]["link_up"] is False


# ---------------------------
#   get_systemstats family
# ---------------------------
def test_select_stat_graph_names_includes_interface_when_present() -> None:
    """The interface graph is included whenever interfaces exist."""
    coord = _bare_coordinator()
    coord.ds = {"interface": {"eth0": {}}}
    coord._is_virtual = False
    coord._systemstats_errored = {}
    names = coord._select_stat_graph_names()
    assert "interface" in names
    assert "cputemp" in names


def test_select_stat_graph_names_removes_cputemp_for_virtual() -> None:
    """A virtual machine drops cputemp, and no interfaces drops the interface graph."""
    coord = _bare_coordinator()
    coord.ds = {"interface": {}}
    coord._is_virtual = True
    coord._systemstats_errored = {}
    names = coord._select_stat_graph_names()
    assert "cputemp" not in names
    assert "interface" not in names


def test_select_stat_graph_names_filters_cooldown_graphs() -> None:
    """A graph that recently errored is excluded while still in its cooldown."""
    coord = _bare_coordinator()
    coord.ds = {"interface": {}}
    coord._is_virtual = False
    coord._systemstats_errored = {"cpu": dt_util.utcnow()}
    coord._systemstats_error_cooldown = timedelta(minutes=10)
    names = coord._select_stat_graph_names()
    assert "cpu" not in names


async def test_fetch_stat_graphs_collects_and_records_failures() -> None:
    """Successful graph queries are collected and failed ones are recorded."""
    coord = _bare_coordinator()
    coord.host = "truenas.local"
    coord._systemstats_errored = {}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(side_effect=[[{"name": "load"}], None])
    result = await coord._fetch_stat_graphs(["load", "cpu"], {"start": 0, "end": 1})
    assert result == [{"name": "load"}]
    assert "cpu" in coord._systemstats_errored


def test_record_failed_graphs_logs_only_new_failures(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Only a graph not already in the errored dict is warned about (new failure)."""
    coord = _bare_coordinator()
    coord.host = "truenas.local"
    coord._systemstats_errored = {"cpu": dt_util.utcnow()}
    with caplog.at_level("WARNING"):
        coord._record_failed_graphs(["cpu", "memory"])
    assert "memory" in caplog.text
    assert coord._systemstats_errored.keys() == {"cpu", "memory"}


def test_record_failed_graphs_noop_for_empty_list() -> None:
    """An empty failed-graphs list leaves the errored dict untouched."""
    coord = _bare_coordinator()
    coord._systemstats_errored = {}
    coord._record_failed_graphs([])
    assert coord._systemstats_errored == {}


def test_process_system_stat_dispatches_by_name() -> None:
    """A "load" stat item with no aggregations falls back to storing the bare name."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {}, "interface": {}}
    # Missing "aggregations"/"legend" fails the isinstance guard in
    # _systemstats_process, so it falls back to _store_stat_defaults, which
    # (for t != "cpu") stores the bare arr name, not a "load_"-prefixed one.
    coord._process_system_stat({"name": "load"})
    assert coord.ds["system_info"]["shortterm"] == 0.0


def test_process_system_stat_ignores_missing_name() -> None:
    """A stat item without a "name" key is ignored instead of raising."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {}}
    coord._process_system_stat({})  # must not raise


def test_process_system_stat_dispatches_cputemp() -> None:
    """A "cputemp" stat item is dispatched to _process_cputemp."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {}}
    item = {"name": "cputemp", "aggregations": {"mean": {"core0": 40.0}}}
    with patch.object(coord, "_process_cputemp") as mock:
        coord._process_system_stat(item)
    mock.assert_called_once_with(item)


def test_process_system_stat_dispatches_cpu_and_rounds_usage() -> None:
    """A "cpu" stat item derives cpu_usage from the (defaulted) cpu_cpu value."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {}}
    coord._process_system_stat({"name": "cpu"})
    # No aggregations/legend -> _store_stat_defaults zeroes cpu_cpu, which then
    # feeds cpu_usage.
    assert coord.ds["system_info"]["cpu_usage"] == pytest.approx(0.0)


def test_process_system_stat_dispatches_interface_for_known_identifier() -> None:
    """An interface stat item for a tracked identifier updates its rx/tx values."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {}, "interface": {"eth0": {}}}
    coord._process_system_stat(
        {"name": "interface", "identifier": "eth0", "legend": "not-a-list"}
    )
    assert coord.ds["interface"]["eth0"]["rx"] == 0.0
    assert coord.ds["interface"]["eth0"]["tx"] == 0.0


def test_process_system_stat_ignores_interface_for_unknown_identifier() -> None:
    """An interface stat item for an untracked identifier is ignored."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {}, "interface": {}}
    coord._process_system_stat({"name": "interface", "identifier": "eth99"})
    assert coord.ds["interface"] == {}


def test_process_system_stat_dispatches_memory() -> None:
    """A "memory" stat item is dispatched to the memory-specific processor."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {"physmem": 1000}}
    coord._process_system_stat(
        {
            "name": "memory",
            "legend": ["available"],
            "aggregations": {"mean": {"available": 250.0}},
        }
    )
    assert coord.ds["system_info"]["memory-free_value"] == 250


def test_process_system_stat_dispatches_arcsize() -> None:
    """An "arcsize" stat item is stored under the dedicated ARC cache key."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {}}
    coord._process_system_stat(
        {
            "name": "arcsize",
            "legend": ["size"],
            "aggregations": {"mean": {"size": 12.345}},
        }
    )
    assert coord.ds["system_info"]["cache_size-arc_value"] == pytest.approx(12.35)


def test_process_system_stat_dispatches_unknown_name() -> None:
    """An unrecognized stat name is recorded in the unknown-stat-names set."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {}}
    coord.host = "truenas.local"
    coord._unknown_system_stat_names = set()
    coord._process_system_stat({"name": "weird_stat"})
    assert "weird_stat" in coord._unknown_system_stat_names


def test_process_cputemp_stores_max_mean() -> None:
    """cpu_temperature is set to the highest mean core temperature."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {}}
    coord._process_cputemp({"aggregations": {"mean": {"core0": 40.0, "core1": 45.0}}})
    assert coord.ds["system_info"]["cpu_temperature"] == 45.0


def test_process_cputemp_none_when_no_valid_means() -> None:
    """An empty means dict leaves cpu_temperature as None."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {}}
    coord._process_cputemp({"aggregations": {"mean": {}}})
    assert coord.ds["system_info"]["cpu_temperature"] is None


def test_process_memory_stat_computes_usage_percent() -> None:
    """Memory total/free/usage-percent are all derived from physmem and available."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {"physmem": 1000}}
    coord._process_memory_stat(
        {"legend": ["available"], "aggregations": {"mean": {"available": 250.0}}}
    )
    assert coord.ds["system_info"]["memory-total_value"] == 1000
    assert coord.ds["system_info"]["memory-free_value"] == 250
    assert coord.ds["system_info"]["memory-usage_percent"] == 75


def test_handle_unknown_stat_logs_once_and_detects_near_miss(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A repeated unknown stat name is only logged once, not on every call."""
    coord = _bare_coordinator()
    coord.host = "truenas.local"
    coord._unknown_system_stat_names = set()
    with caplog.at_level("DEBUG"):
        coord._handle_unknown_stat("cpu_usage")
        coord._handle_unknown_stat("cpu_usage")
    assert caplog.text.count("unknown system stat graph name") == 1


def test_process_system_stat_interface_updates_rx_tx() -> None:
    """Valid received/sent means update the interface's rx/tx to positive values."""
    coord = _bare_coordinator()
    coord.ds = {"interface": {"eth0": {}}}
    item = {
        "legend": ["received", "sent"],
        "aggregations": {"mean": {"received": 100.0, "sent": 50.0}},
    }
    coord._process_system_stat_interface(item, "eth0")
    assert coord.ds["interface"]["eth0"]["rx"] > 0
    assert coord.ds["interface"]["eth0"]["tx"] > 0


def test_process_system_stat_interface_zeroes_on_invalid_legend() -> None:
    """A non-list legend zeroes the interface's rx/tx instead of raising."""
    coord = _bare_coordinator()
    coord.ds = {"interface": {"eth0": {}}}
    coord._process_system_stat_interface({"legend": "not-a-list"}, "eth0")
    assert coord.ds["interface"]["eth0"]["rx"] == 0.0
    assert coord.ds["interface"]["eth0"]["tx"] == 0.0


def test_process_system_stat_interface_zeroes_when_mean_not_dict() -> None:
    """A non-dict aggregations.mean zeroes the interface's rx/tx instead of raising."""
    coord = _bare_coordinator()
    coord.ds = {"interface": {"eth0": {}}}
    item = {
        "legend": ["received", "sent"],
        "aggregations": {"mean": "not-a-dict"},
    }
    coord._process_system_stat_interface(item, "eth0")
    assert coord.ds["interface"]["eth0"]["rx"] == 0.0
    assert coord.ds["interface"]["eth0"]["tx"] == 0.0


async def test_get_systemstats_returns_early_without_graph_names() -> None:
    """No selectable graph names (all in cooldown) skips the API query entirely."""
    coord = _bare_coordinator()
    coord.ds = {"interface": {}}
    coord._is_virtual = True
    coord._systemstats_errored = {
        name: dt_util.utcnow() for name in ("load", "cpu", "arcsize", "memory")
    }
    coord._systemstats_error_cooldown = timedelta(minutes=10)
    coord.config_entry = MagicMock()
    coord.config_entry.options = {}
    coord.api = MagicMock()
    coord.api.query = AsyncMock()
    await coord.get_systemstats()
    coord.api.query.assert_not_awaited()


async def test_get_systemstats_returns_when_fetch_yields_no_graphs() -> None:
    """A None graph-fetch response leaves system_info untouched."""
    coord = _bare_coordinator()
    coord.ds = {"interface": {}, "system_info": {}}
    coord._is_virtual = True
    coord._systemstats_errored = {}
    coord.host = "truenas.local"
    coord.config_entry = MagicMock()
    coord.config_entry.options = {}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value=None)
    await coord.get_systemstats()
    assert coord.ds["system_info"] == {}


async def test_get_systemstats_processes_returned_graphs() -> None:
    """Graphs returned by the API are processed into system_info values."""
    coord = _bare_coordinator()
    coord.ds = {"interface": {}, "system_info": {}}
    coord._is_virtual = True
    coord._systemstats_errored = {}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value=[{"name": "load"}])
    await coord.get_systemstats()
    assert coord.ds["system_info"]["shortterm"] == 0.0


# ---------------------------
#   get_service
# ---------------------------
# The running/display_name derivation this test used to exercise directly
# now lives in and is tested by aiotruenas's own TrueNASState.get_service().
# get_service just delegates and assigns the result, so this only needs to
# lock in that plumbing.
async def test_get_service_delegates_to_state() -> None:
    """get_service assigns TrueNASState.get_service()'s result, str-keyed."""
    coord = _bare_coordinator()
    coord.ds = {"service": {}}
    coord.state = MagicMock()
    coord.state.get_service = AsyncMock(
        return_value={1: {"running": True, "display_name": "SMB"}}
    )
    await coord.get_service()
    assert coord.ds["service"]["1"]["running"] is True
    assert coord.ds["service"]["1"]["display_name"] == "SMB"


# ---------------------------
#   get_pool
# ---------------------------
# The pool capacity/mountpoint-matching/boot-pool-merge/topology-error-
# aggregation logic these tests used to exercise directly now lives in and is
# tested by aiotruenas's own TrueNASState.get_pool(). get_pool just delegates
# and assigns the result, so this only needs to lock in that plumbing.
async def test_get_pool_delegates_to_state() -> None:
    """get_pool assigns TrueNASState.get_pool()'s result, str-keyed."""
    coord = _bare_coordinator()
    coord.ds = {"pool": {}}
    coord.state = MagicMock()
    coord.state.get_pool = AsyncMock(
        return_value={"g1": {"name": "tank", "available": 40, "total": 100}}
    )
    await coord.get_pool()
    assert coord.ds["pool"]["g1"]["available"] == 40
    assert coord.ds["pool"]["g1"]["total"] == 100


# ---------------------------
#   get_dataset
# ---------------------------
async def test_get_dataset_empty_when_group_not_monitored() -> None:
    """An unmonitored datasets group clears the dict without querying the state layer."""
    coord = _bare_coordinator()
    coord.ds = {"dataset": {"stale": {}}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: []}
    coord.state = MagicMock()
    coord.state.get_dataset = AsyncMock()
    await coord.get_dataset()
    assert coord.ds["dataset"] == {}
    coord.state.get_dataset.assert_not_awaited()


async def test_get_dataset_returns_empty_when_none_found() -> None:
    """An empty datasets response leaves the dataset dict empty."""
    coord = _bare_coordinator()
    coord.ds = {"dataset": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: [MONITOR_GROUP_DATASETS]}
    coord.state = MagicMock()
    coord.state.get_dataset = AsyncMock(return_value={})
    await coord.get_dataset()
    assert coord.ds["dataset"] == {}


async def test_get_dataset_parses_when_monitored() -> None:
    """A monitored datasets group assigns TrueNASState.get_dataset()'s result."""
    coord = _bare_coordinator()
    coord.ds = {"dataset": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: [MONITOR_GROUP_DATASETS]}
    coord.state = MagicMock()
    coord.state.get_dataset = AsyncMock(
        return_value={"tank": {"id": "tank", "type": "FILESYSTEM", "name": "tank"}}
    )
    await coord.get_dataset()
    assert "tank" in coord.ds["dataset"]


# ---------------------------
#   get_disk
# ---------------------------
# The disk.query normalization and netdata/API-fallback temperature-
# enrichment logic these tests used to exercise directly now lives in and is
# tested by aiotruenas's own TrueNASState.get_disk(). get_disk just
# delegates and assigns the result, so this only needs to lock in that
# plumbing.
async def test_get_disk_delegates_to_state() -> None:
    """get_disk assigns TrueNASState.get_disk()'s result, str-keyed."""
    coord = _bare_coordinator()
    coord.ds = {"disk": {}}
    coord.state = MagicMock()
    coord.state.get_disk = AsyncMock(
        return_value={"disk1": {"name": "sda", "temperature": 35.0}}
    )
    await coord.get_disk()
    assert coord.ds["disk"]["disk1"]["temperature"] == 35.0


# ---------------------------
#   get_vm
# ---------------------------
# The memory/running derivation these tests used to exercise directly now
# lives in and is tested by aiotruenas's own TrueNASState.get_vm(). get_vm
# just delegates and assigns the result, so this only needs to lock in that
# plumbing.
async def test_get_vm_empty_when_not_monitored() -> None:
    """An unmonitored VMs group clears the dict without querying the state layer."""
    coord = _bare_coordinator()
    coord.ds = {"vm": {"stale": {}}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: []}
    coord.state = MagicMock()
    coord.state.get_vm = AsyncMock()
    await coord.get_vm()
    assert coord.ds["vm"] == {}
    coord.state.get_vm.assert_not_awaited()


async def test_get_vm_delegates_to_state() -> None:
    """get_vm assigns TrueNASState.get_vm()'s result, str-keyed."""
    coord = _bare_coordinator()
    coord.ds = {"vm": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: [MONITOR_GROUP_VMS]}
    coord.state = MagicMock()
    coord.state.get_vm = AsyncMock(return_value={1: {"memory": 2, "running": True}})
    await coord.get_vm()
    assert coord.ds["vm"]["1"]["memory"] == 2
    assert coord.ds["vm"]["1"]["running"] is True


# ---------------------------
#   get_container
# ---------------------------
# The CONTAINER-type filtering and cpu/memory/running/ip_address derivation
# these tests used to exercise directly now lives in and is tested by
# aiotruenas's own TrueNASState.get_container() (which also dispatches
# between the legacy virt.instance.query and TrueNAS-26.0+ container.query
# based on its own version detection). get_container just delegates and
# assigns the result, so this only needs to lock in that plumbing.
async def test_get_container_empty_when_not_monitored() -> None:
    """An unmonitored containers group clears the dict without querying the state layer."""
    coord = _bare_coordinator()
    coord.ds = {"container": {"stale": {}}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: []}
    coord.state = MagicMock()
    coord.state.get_container = AsyncMock()
    await coord.get_container()
    assert coord.ds["container"] == {}
    coord.state.get_container.assert_not_awaited()


async def test_get_container_delegates_to_state() -> None:
    """get_container assigns TrueNASState.get_container()'s result, str-keyed."""
    coord = _bare_coordinator()
    coord.ds = {"container": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: [MONITOR_GROUP_CONTAINERS]}
    coord.state = MagicMock()
    coord.state.get_container = AsyncMock(
        return_value={"c1": {"cpu": 1, "memory": 1, "running": True}}
    )
    await coord.get_container()
    assert coord.ds["container"]["c1"]["cpu"] == 1
    assert coord.ds["container"]["c1"]["running"] is True


# ---------------------------
#   get_directoryservices
# ---------------------------
# The config+status merge and healthy derivation these tests used to
# exercise directly now lives in and is tested by aiotruenas's own
# TrueNASState.get_directoryservices(). get_directoryservices just delegates
# and assigns the result, so this only needs to lock in that plumbing.
async def test_get_directoryservices_empty_when_not_monitored() -> None:
    """An unmonitored directory-services group clears the dict without querying."""
    coord = _bare_coordinator()
    coord.ds = {"directoryservices": {"stale": {}}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: []}
    coord.state = MagicMock()
    coord.state.get_directoryservices = AsyncMock()
    await coord.get_directoryservices()
    assert coord.ds["directoryservices"] == {}
    coord.state.get_directoryservices.assert_not_awaited()


async def test_get_directoryservices_delegates_to_state() -> None:
    """get_directoryservices assigns TrueNASState.get_directoryservices()'s result."""
    coord = _bare_coordinator()
    coord.ds = {"directoryservices": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {
        CONF_MONITORED_GROUPS: [MONITOR_GROUP_DIRECTORY_SERVICES]
    }
    coord.state = MagicMock()
    coord.state.get_directoryservices = AsyncMock(
        return_value={1: {"status": "HEALTHY", "healthy": True}}
    )
    await coord.get_directoryservices()
    assert coord.ds["directoryservices"]["1"]["healthy"] is True


# ---------------------------
#   get_certificates
# ---------------------------
async def test_get_certificates_computes_days_until_expiry() -> None:
    """A certificate's days_until_expiry is computed from its "until" timestamp."""
    coord = _bare_coordinator()
    coord.ds = {}
    coord.api = MagicMock()
    future = dt_util.utcnow() + timedelta(days=10)
    coord.api.query = AsyncMock(
        return_value=[
            {
                "id": 1,
                "name": "cert1",
                "cert_type": "CERTIFICATE",
                "until": future.strftime("%c"),
            }
        ]
    )
    await coord.get_certificates()
    assert coord.ds["certificate"]["cert1"]["days_until_expiry"] in (9, 10)


async def test_get_certificates_none_expiry_when_until_missing() -> None:
    """A certificate without an "until" field gets a None days_until_expiry."""
    coord = _bare_coordinator()
    coord.ds = {}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value=[{"id": 1, "name": "cert1"}])
    await coord.get_certificates()
    assert coord.ds["certificate"]["cert1"]["days_until_expiry"] is None


# ---------------------------
#   get_arc
# ---------------------------
# The netdata-graph querying/mean-value computation these tests used to
# exercise directly now lives in and is tested by aiotruenas's own
# TrueNASState.get_arc(). get_arc just delegates and assigns the result, so
# this only needs to lock in that plumbing.
async def test_get_arc_delegates_to_state() -> None:
    """get_arc assigns TrueNASState.get_arc()'s result verbatim."""
    coord = _bare_coordinator()
    coord.ds = {}
    coord.state = MagicMock()
    coord.state.get_arc = AsyncMock(
        return_value={
            "data_hit_percent": 90.0,
            "metadata_hit_percent": None,
            "l2_hit_percent": None,
        }
    )
    await coord.get_arc()
    assert coord.ds["arc"]["data_hit_percent"] == 90.0


# ---------------------------
#   get_ups
# ---------------------------
# The netdata UPS-graph discovery/caching and per-metric value computation
# these tests used to exercise directly now lives in and is tested by
# aiotruenas's own TrueNASState.get_ups(). get_ups just delegates and
# assigns the result, so this only needs to lock in that plumbing.
async def test_get_ups_empty_when_not_monitored() -> None:
    """An unmonitored UPS group clears the dict without querying the state layer."""
    coord = _bare_coordinator()
    coord.ds = {"ups": {"stale": 1}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: []}
    coord.state = MagicMock()
    coord.state.get_ups = AsyncMock()
    await coord.get_ups()
    assert coord.ds["ups"] == {}
    coord.state.get_ups.assert_not_awaited()


async def test_get_ups_delegates_to_state() -> None:
    """get_ups assigns TrueNASState.get_ups()'s result verbatim."""
    coord = _bare_coordinator()
    coord.ds = {"ups": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: [MONITOR_GROUP_UPS]}
    coord.state = MagicMock()
    coord.state.get_ups = AsyncMock(return_value={"battery_charge": 80.0})
    await coord.get_ups()
    assert coord.ds["ups"]["battery_charge"] == 80.0


# ---------------------------
#   get_cloudsync / get_replication / get_rsync / get_snapshottask / get_scrub
# ---------------------------
# The response normalization (incl. replication's job.state fallback) these
# tests used to exercise directly now lives in and is tested by aiotruenas's
# own TrueNASState.get_cloudsync()/get_replication()/get_rsync()/
# get_snapshottask()/get_scrub(). Each get_* method just delegates and
# assigns the (str-keyed) result, so these only need to lock in that
# plumbing.
async def test_get_cloudsync_empty_when_not_monitored() -> None:
    """An unmonitored cloudsync group clears the dict without querying the state layer."""
    coord = _bare_coordinator()
    coord.ds = {"cloudsync": {"stale": {}}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: []}
    coord.state = MagicMock()
    coord.state.get_cloudsync = AsyncMock()
    await coord.get_cloudsync()
    assert coord.ds["cloudsync"] == {}
    coord.state.get_cloudsync.assert_not_awaited()


async def test_get_cloudsync_delegates_to_state() -> None:
    """get_cloudsync assigns TrueNASState.get_cloudsync()'s result, str-keyed."""
    coord = _bare_coordinator()
    coord.ds = {"cloudsync": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: [MONITOR_GROUP_CLOUDSYNC]}
    coord.state = MagicMock()
    coord.state.get_cloudsync = AsyncMock(
        return_value={"cs1": {"id": "cs1", "description": "backup"}}
    )
    await coord.get_cloudsync()
    assert "cs1" in coord.ds["cloudsync"]


async def test_get_replication_empty_when_not_monitored() -> None:
    """An unmonitored replication group clears the dict without querying the state layer."""
    coord = _bare_coordinator()
    coord.ds = {"replication": {"stale": {}}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: []}
    coord.state = MagicMock()
    coord.state.get_replication = AsyncMock()
    await coord.get_replication()
    assert coord.ds["replication"] == {}
    coord.state.get_replication.assert_not_awaited()


async def test_get_replication_delegates_to_state() -> None:
    """get_replication assigns TrueNASState.get_replication()'s result, str-keyed."""
    coord = _bare_coordinator()
    coord.ds = {"replication": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: [MONITOR_GROUP_REPLICATION]}
    coord.state = MagicMock()
    coord.state.get_replication = AsyncMock(
        return_value={1: {"id": 1, "name": "repl1", "state": "RUNNING"}}
    )
    await coord.get_replication()
    assert coord.ds["replication"]["1"]["state"] == "RUNNING"


async def test_get_rsync_empty_when_not_monitored() -> None:
    """An unmonitored rsync group clears the dict without querying the state layer."""
    coord = _bare_coordinator()
    coord.ds = {"rsynctask": {"stale": {}}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: []}
    coord.state = MagicMock()
    coord.state.get_rsync = AsyncMock()
    await coord.get_rsync()
    assert coord.ds["rsynctask"] == {}
    coord.state.get_rsync.assert_not_awaited()


async def test_get_rsync_delegates_to_state() -> None:
    """get_rsync assigns TrueNASState.get_rsync()'s result, str-keyed."""
    coord = _bare_coordinator()
    coord.ds = {"rsynctask": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: [MONITOR_GROUP_RSYNC]}
    coord.state = MagicMock()
    coord.state.get_rsync = AsyncMock(return_value={1: {"id": 1, "path": "/mnt/tank"}})
    await coord.get_rsync()
    assert "1" in coord.ds["rsynctask"]


async def test_get_snapshottask_empty_when_not_monitored() -> None:
    """An unmonitored snapshots group clears the dict without querying the state layer."""
    coord = _bare_coordinator()
    coord.ds = {"snapshottask": {"stale": {}}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: []}
    coord.state = MagicMock()
    coord.state.get_snapshottask = AsyncMock()
    await coord.get_snapshottask()
    assert coord.ds["snapshottask"] == {}
    coord.state.get_snapshottask.assert_not_awaited()


async def test_get_snapshottask_delegates_to_state() -> None:
    """get_snapshottask assigns TrueNASState.get_snapshottask()'s result, str-keyed."""
    coord = _bare_coordinator()
    coord.ds = {"snapshottask": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: [MONITOR_GROUP_SNAPSHOTS]}
    coord.state = MagicMock()
    schedule = {"minute": "0", "hour": "*", "dom": "*", "month": "*", "dow": "*"}
    coord.state.get_snapshottask = AsyncMock(
        return_value={1: {"id": 1, "dataset": "tank/data", "schedule": schedule}}
    )
    await coord.get_snapshottask()
    assert "1" in coord.ds["snapshottask"]
    assert coord.ds["snapshottask"]["1"]["schedule"] == schedule


async def test_get_scrub_delegates_to_state() -> None:
    """get_scrub assigns TrueNASState.get_scrub()'s result, str-keyed."""
    coord = _bare_coordinator()
    coord.ds = {"scrub": {}}
    coord.state = MagicMock()
    coord.state.get_scrub = AsyncMock(return_value={1: {"id": 1, "pool_name": "tank"}})
    await coord.get_scrub()
    assert "1" in coord.ds["scrub"]


# ---------------------------
#   get_app / _clear_finished_app_updates
# ---------------------------
# The running/update_available derivation (catalog upgrade_available vs.
# custom-app image_updates_available fallback) these tests used to exercise
# directly now lives in and is tested by aiotruenas's own
# TrueNASState.get_app(). get_app just delegates and assigns the result, so
# this only needs to lock in that plumbing plus the update_jobid
# carry-forward (see get_app's docstring: TrueNASState.get_app() never
# carries this HA-only field, so it is preserved by hand across polls).
async def test_get_app_delegates_to_state() -> None:
    """get_app assigns TrueNASState.get_app()'s result, str-keyed."""
    coord = _bare_coordinator()
    coord.ds = {"app": {}}
    coord.state = MagicMock()
    coord.state.get_app = AsyncMock(
        return_value={"app1": {"running": True, "update_available": True}}
    )
    coord._clear_finished_app_updates = AsyncMock()
    await coord.get_app()
    assert coord.ds["app"]["app1"]["running"] is True
    assert coord.ds["app"]["app1"]["update_available"] is True
    assert coord.ds["app"]["app1"]["update_jobid"] == 0


async def test_get_app_carries_forward_update_jobid() -> None:
    """An in-progress upgrade job's update_jobid must survive across a poll.

    TrueNASState.get_app() returns a freshly-built dict that never carries
    this HA-specific field; losing it would strand app upgrade-job tracking
    (_clear_finished_app_updates) forever on the next poll.
    """
    coord = _bare_coordinator()
    coord.ds = {"app": {"app1": {"update_jobid": 5}}}
    coord.state = MagicMock()
    coord.state.get_app = AsyncMock(return_value={"app1": {"running": True}})
    coord._clear_finished_app_updates = AsyncMock()
    await coord.get_app()
    assert coord.ds["app"]["app1"]["update_jobid"] == 5


async def test_clear_finished_app_updates_resets_when_not_running() -> None:
    """A SUCCESS-state update job resets the app's update_jobid to zero."""
    coord = _bare_coordinator()
    coord.ds = {"app": {"app1": {"update_jobid": 5}}}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value=[{"state": "SUCCESS"}])
    await coord._clear_finished_app_updates()
    assert coord.ds["app"]["app1"]["update_jobid"] == 0


async def test_clear_finished_app_updates_keeps_running_job() -> None:
    """A RUNNING update job leaves the app's update_jobid untouched."""
    coord = _bare_coordinator()
    coord.ds = {"app": {"app1": {"update_jobid": 5}}}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value=[{"state": "RUNNING"}])
    await coord._clear_finished_app_updates()
    assert coord.ds["app"]["app1"]["update_jobid"] == 5


async def test_clear_finished_app_updates_skips_without_jobid() -> None:
    """A zero update_jobid skips the job-status query entirely."""
    coord = _bare_coordinator()
    coord.ds = {"app": {"app1": {"update_jobid": 0}}}
    coord.api = MagicMock()
    coord.api.query = AsyncMock()
    await coord._clear_finished_app_updates()
    coord.api.query.assert_not_awaited()


# ---------------------------
#   app.stats subscription helpers
# ---------------------------
def test_get_app_identifier_prefers_name() -> None:
    """The "name" field is preferred over the legacy "app_name" field."""
    coord = _bare_coordinator()
    assert coord._get_app_identifier({"name": "app1", "app_name": "legacy"}) == "app1"


def test_get_app_identifier_falls_back_to_app_name() -> None:
    """Without a "name" field, the legacy "app_name" field is used instead."""
    coord = _bare_coordinator()
    assert coord._get_app_identifier({"app_name": "legacy"}) == "legacy"


def test_get_app_identifier_returns_none_when_missing() -> None:
    """With neither "name" nor "app_name" present, None is returned."""
    coord = _bare_coordinator()
    assert coord._get_app_identifier({}) is None


def test_resolve_app_stats_event_name_uses_poll_interval() -> None:
    """The event name embeds the configured poll interval."""
    coord = _bare_coordinator()
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_POLL_INTERVAL: 30}
    assert coord._resolve_app_stats_event_name() == 'app.stats:{"interval": 30}'


def test_resolve_app_stats_event_name_falls_back_on_invalid_value() -> None:
    """A non-numeric poll interval falls back to the default interval."""
    coord = _bare_coordinator()
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_POLL_INTERVAL: "bad"}
    assert (
        coord._resolve_app_stats_event_name()
        == f'app.stats:{{"interval": {DEFAULT_POLL_INTERVAL}}}'
    )


async def test_stop_app_stats_if_active_stops_when_subscribed() -> None:
    """An active subscription is force-stopped."""
    coord = _bare_coordinator()
    coord._app_stats_sub_id = "sub-1"
    coord.stop_app_stats = AsyncMock()
    await coord._stop_app_stats_if_active()
    coord.stop_app_stats.assert_awaited_once_with(force=True)


async def test_stop_app_stats_if_active_noop_when_not_subscribed() -> None:
    """No active subscription means stop_app_stats is never called."""
    coord = _bare_coordinator()
    coord._app_stats_sub_id = None
    coord.stop_app_stats = AsyncMock()
    await coord._stop_app_stats_if_active()
    coord.stop_app_stats.assert_not_awaited()


async def test_maybe_teardown_changed_app_stats_subscription_stops_on_change() -> None:
    """A changed event name tears down the existing subscription."""
    coord = _bare_coordinator()
    coord._app_stats_event_name = "old"
    coord.stop_app_stats = AsyncMock()
    await coord._maybe_teardown_changed_app_stats_subscription("new")
    coord.stop_app_stats.assert_awaited_once_with(force=True)


async def test_maybe_clear_inactive_app_stats_subscription_clears_when_inactive() -> (
    None
):
    """An inactive subscription id (per the API) is cleared locally."""
    coord = _bare_coordinator()
    coord._app_stats_sub_id = "sub-1"
    coord.api = MagicMock()
    coord.api.is_subscribed = AsyncMock(return_value=False)
    await coord._maybe_clear_inactive_app_stats_subscription()
    assert coord._app_stats_sub_id is None


async def test_subscribe_to_app_stats_handles_missing_sub_id() -> None:
    """A None subscription id from subscribe_events leaves it unset."""
    coord = _bare_coordinator()
    coord.api = MagicMock()
    coord.api.subscribe_events = AsyncMock(return_value=(None, None))
    await coord._subscribe_to_app_stats("event")
    assert coord._app_stats_sub_id is None


async def test_subscribe_to_app_stats_handles_exception() -> None:
    """A subscribe_events exception is swallowed instead of propagating."""
    coord = _bare_coordinator()
    coord.api = MagicMock()
    coord.api.subscribe_events = AsyncMock(side_effect=Exception("boom"))
    await coord._subscribe_to_app_stats("event")  # must not raise
    assert coord._app_stats_sub_id is None


async def test_stop_app_stats_unsubscribe_exception_still_clears_state(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An unsubscribe_events exception still clears the local subscription id."""
    coord = _bare_coordinator()
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.unsubscribe_events = AsyncMock(side_effect=Exception("boom"))
    coord._app_stats_sub_id = "sub-1"
    with caplog.at_level("DEBUG"):
        await coord.stop_app_stats()
    assert coord._app_stats_sub_id is None


async def test_stop_app_stats_not_connected_no_force_is_noop() -> None:
    """A disconnected API without force=True leaves the subscription state as-is."""
    coord = _bare_coordinator()
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=False)
    coord._app_stats_sub_id = "sub-1"
    coord._app_stats_event_name = "event"
    await coord.stop_app_stats(force=False)
    assert coord._app_stats_sub_id == "sub-1"


def test_coerce_float_handles_invalid_values() -> None:
    """Unparsable values yield None, a parsable numeric string yields a float."""
    coord = _bare_coordinator()
    assert coord._coerce_float(None) is None
    assert coord._coerce_float("bad") is None
    assert coord._coerce_float("3.5") == pytest.approx(3.5)


def test_collect_current_app_names_uses_identifier() -> None:
    """Only dict app entries contribute their identifier to the name set."""
    coord = _bare_coordinator()
    coord.ds = {"app": {"a": {"name": "app1"}, "b": "not-a-dict"}}
    assert coord._collect_current_app_names() == {"app1"}


def test_prune_stale_app_stats_removes_missing_entries() -> None:
    """Stats for apps outside the given current-names set are removed."""
    coord = _bare_coordinator()
    coord.ds = {"app_stats": {"app1": {}, "stale": {}}}
    coord._prune_stale_app_stats({"app1"})
    assert coord.ds["app_stats"] == {"app1": {}}


# ---------------------------
#   get_cronjob
# ---------------------------
async def test_get_cronjob_empty_when_not_monitored() -> None:
    """An unmonitored cronjobs group clears the dict without querying the state layer."""
    coord = _bare_coordinator()
    coord.ds = {"cronjob": {"stale": {}}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: []}
    coord.state = MagicMock()
    coord.state.get_cronjob = AsyncMock()
    await coord.get_cronjob()
    assert coord.ds["cronjob"] == {}
    coord.state.get_cronjob.assert_not_awaited()


# display_name derivation now lives in and is tested by aiotruenas's own
# TrueNASState.get_cronjob(); the "skip disabled" filter below stays local
# (an HA options-flow behavior), so these tests mock the delegated result
# and lock in only the filtering plumbing.
async def test_get_cronjob_skips_disabled_by_default_behavior() -> None:
    """With the skip-disabled behavior enabled, disabled cronjobs are excluded."""
    coord = _bare_coordinator()
    coord.ds = {"cronjob": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {
        CONF_MONITORED_GROUPS: [MONITOR_GROUP_CRONJOBS],
        CONF_BEHAVIORS: [BEHAVIOR_SKIP_DISABLED_CRONJOBS],
    }
    coord.state = MagicMock()
    coord.state.get_cronjob = AsyncMock(
        return_value={
            1: {"enabled": True, "display_name": "Job A"},
            2: {"enabled": False, "display_name": "Job B"},
        }
    )
    await coord.get_cronjob()
    assert "1" in coord.ds["cronjob"]
    assert "2" not in coord.ds["cronjob"]
    assert coord.ds["cronjob"]["1"]["display_name"] == "Job A"


async def test_get_cronjob_keeps_disabled_when_behavior_off() -> None:
    """With the skip-disabled behavior off, disabled cronjobs are still kept."""
    coord = _bare_coordinator()
    coord.ds = {"cronjob": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {
        CONF_MONITORED_GROUPS: [MONITOR_GROUP_CRONJOBS],
        CONF_BEHAVIORS: [],
    }
    coord.state = MagicMock()
    coord.state.get_cronjob = AsyncMock(
        return_value={2: {"enabled": False, "display_name": "ls"}}
    )
    await coord.get_cronjob()
    assert coord.ds["cronjob"]["2"]["display_name"] == "ls"


async def test_get_cronjob_falls_back_to_legacy_option_when_behaviors_absent() -> None:
    """Without CONF_BEHAVIORS set, the legacy cronjob_skip_disabled option is used."""
    coord = _bare_coordinator()
    coord.ds = {"cronjob": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {
        CONF_MONITORED_GROUPS: [MONITOR_GROUP_CRONJOBS],
        "cronjob_skip_disabled": False,
    }
    coord.config_entry.data = {}
    coord.state = MagicMock()
    coord.state.get_cronjob = AsyncMock(
        return_value={3: {"enabled": False, "display_name": "Cronjob 3"}}
    )
    await coord.get_cronjob()
    assert coord.ds["cronjob"]["3"]["display_name"] == "Cronjob 3"
