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
    CONF_STATISTICS_CLEANUP_IGNORED,
    DEFAULT_DEVICE_NAME,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    LEGACY_DOMAIN,
    MIGRATION_LEGACY_ENTRY_ID,
    MIGRATION_RECORDS,
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
    _accumulate_vdev_errors,
    _aggregate_topology_errors,
    _arc_value,
    _as_int,
    _count_statistics_with_data,
    _first_ipv4,
    _is_truenas_sensor_id,
    _median,
    _netdata_mean_value,
    _stat_name_similar,
    _to_int,
    _unwrap_app_stats_message,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util, slugify


def _bare_coordinator() -> TrueNASCoordinator:
    """Build a TrueNASCoordinator without running its hass-dependent __init__."""
    coord = TrueNASCoordinator.__new__(TrueNASCoordinator)
    coord._app_stats_event_name = None
    coord._app_stats_sub_id = None
    coord.orphaned_statistics = []
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
#   _median
# ---------------------------
def test_median_odd_count() -> None:
    """The median of an odd-length list is its middle value."""
    assert _median([3.0, 1.0, 2.0]) == pytest.approx(2.0)


def test_median_even_count() -> None:
    """The median of an even-length list is the mean of its two middle values."""
    assert _median([1.0, 2.0, 3.0, 4.0]) == pytest.approx(2.5)


def test_median_single_value() -> None:
    """The median of a single-value list is that value."""
    assert _median([42.0]) == pytest.approx(42.0)


def test_median_empty_list_raises_index_error() -> None:
    """Empty input is outside _median's contract (docstring: non-empty list).

    Its only caller guards with a non-empty check. Lock in the current
    fail-loud behaviour instead of silently returning a value.
    """
    with pytest.raises(IndexError):
        _median([])


# ---------------------------
#   _as_int / _to_int
# ---------------------------
def test_as_int_returns_int_unchanged() -> None:
    """An int value passes through _as_int unchanged."""
    assert _as_int(5) == 5


def test_as_int_returns_zero_for_non_int() -> None:
    """Non-int values (str, None, float) fall back to zero."""
    assert _as_int("5") == 0
    assert _as_int(None) == 0
    assert _as_int(1.5) == 0


def test_to_int_parses_numeric_string() -> None:
    """A numeric string is parsed into its int value."""
    assert _to_int("48") == 48


def test_to_int_falls_back_to_default_on_invalid() -> None:
    """An unparsable value falls back to the given default."""
    assert _to_int("not-a-number", default=7) == 7
    assert _to_int(None, default=7) == 7


# ---------------------------
#   _accumulate_vdev_errors / _aggregate_topology_errors
# ---------------------------
def test_accumulate_vdev_errors_leaf_disk() -> None:
    """A leaf disk vdev's error counts are added to the running totals."""
    totals = {"read": 0, "write": 0, "checksum": 0}
    vdev = {"stats": {"read_errors": 1, "write_errors": 2, "checksum_errors": 3}}
    _accumulate_vdev_errors(vdev, totals)
    assert totals == {"read": 1, "write": 2, "checksum": 3}


def test_accumulate_vdev_errors_recurses_into_children_only() -> None:
    """A mirror vdev's own stats must not be double-counted on top of its disks."""
    totals = {"read": 0, "write": 0, "checksum": 0}
    mirror = {
        "stats": {"read_errors": 99, "write_errors": 99, "checksum_errors": 99},
        "children": [
            {"stats": {"read_errors": 1, "write_errors": 0, "checksum_errors": 0}},
            {"stats": {"read_errors": 0, "write_errors": 1, "checksum_errors": 0}},
        ],
    }
    _accumulate_vdev_errors(mirror, totals)
    assert totals == {"read": 1, "write": 1, "checksum": 0}


def test_accumulate_vdev_errors_ignores_non_dict() -> None:
    """A non-dict vdev leaves the running totals untouched."""
    totals = {"read": 0, "write": 0, "checksum": 0}
    _accumulate_vdev_errors("not-a-dict", totals)
    assert totals == {"read": 0, "write": 0, "checksum": 0}


def test_aggregate_topology_errors_sums_all_categories() -> None:
    """Errors from every topology category (data, cache, ...) are summed."""
    topology = {
        "data": [
            {"stats": {"read_errors": 1, "write_errors": 0, "checksum_errors": 0}}
        ],
        "cache": [
            {"stats": {"read_errors": 0, "write_errors": 2, "checksum_errors": 0}}
        ],
    }
    assert _aggregate_topology_errors(topology) == (1, 2, 0)


def test_aggregate_topology_errors_non_dict_returns_zeros() -> None:
    """A non-dict topology yields an all-zero error tuple."""
    assert _aggregate_topology_errors(None) == (0, 0, 0)


# ---------------------------
#   _netdata_mean_value / _arc_value / _ups_value
# ---------------------------
def test_netdata_mean_value_computes_mean() -> None:
    """The mean of all per-series values in a netdata graph point is returned."""
    graph_data = [{"aggregations": {"mean": {"a": 1.0, "b": 3.0}}}]
    assert _netdata_mean_value(graph_data) == pytest.approx(2.0)


def test_netdata_mean_value_returns_none_for_empty_list() -> None:
    """An empty graph-data list yields None."""
    assert _netdata_mean_value([]) is None


def test_netdata_mean_value_returns_none_for_malformed_item() -> None:
    """Malformed graph-data entries (wrong type/missing keys/empty mean) yield None."""
    assert _netdata_mean_value(["not-a-dict"]) is None
    assert _netdata_mean_value([{"aggregations": {"mean": "not-a-dict"}}]) is None
    assert _netdata_mean_value([{"aggregations": {"mean": {}}}]) is None


def test_arc_value_delegates_to_netdata_mean_value() -> None:
    """_arc_value returns the same mean _netdata_mean_value would compute."""
    graph_data = [{"aggregations": {"mean": {"a": 10.0}}}]
    assert _arc_value(graph_data) == pytest.approx(10.0)


# ---------------------------
#   _first_ipv4
# ---------------------------
def test_first_ipv4_returns_first_inet_address() -> None:
    """The first INET (IPv4) alias address is returned, skipping INET6 entries."""
    aliases = [
        {"type": "INET6", "address": "2001:db8::1"},
        {"type": "INET", "address": "192.0.2.5"},
        {"type": "INET", "address": "192.0.2.6"},
    ]
    assert _first_ipv4(aliases) == "192.0.2.5"


def test_first_ipv4_returns_unknown_when_no_inet() -> None:
    """Missing, empty, or IPv6-only alias lists all fall back to "unknown"."""
    assert _first_ipv4([{"type": "INET6", "address": "2001:db8::1"}]) == "unknown"
    assert _first_ipv4(None) == "unknown"
    assert _first_ipv4([]) == "unknown"


# ---------------------------
#   _is_truenas_sensor_id
# ---------------------------
def test_is_truenas_sensor_id_matches_device_slug_token() -> None:
    """A sensor entity id containing the device slug anywhere is matched."""
    slug = slugify(DEFAULT_DEVICE_NAME)
    assert _is_truenas_sensor_id(f"sensor.{slug}_cpu_usage", slug) is True
    assert _is_truenas_sensor_id(f"sensor.system_{slug}_uptime", slug) is True
    assert _is_truenas_sensor_id(f"sensor.{slug}viacfnoauth_cpu", slug) is True


def test_is_truenas_sensor_id_rejects_other_domains() -> None:
    """A sensor id whose text does not contain the device slug is rejected."""
    slug = slugify(DEFAULT_DEVICE_NAME)
    assert _is_truenas_sensor_id("sensor.unrelated_integration_temp", slug) is False


def test_is_truenas_sensor_id_rejects_non_sensor_entities() -> None:
    """Entities outside the sensor domain (e.g. binary_sensor) are rejected."""
    slug = slugify(DEFAULT_DEVICE_NAME)
    assert _is_truenas_sensor_id(f"binary_sensor.{slug}_online", slug) is False


def test_is_truenas_sensor_id_unaffected_by_domain_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: matching used to depend on DOMAIN/LEGACY_DOMAIN.

    That broke since the 2.0.0 CE rename because DOMAIN ("truenas_ce") contains an
    underscore and can never appear whole inside an underscore-split token.
    The fix matches the device-name slug instead -- the same string real
    entity ids are slugged from -- so behavior no longer depends on
    DOMAIN/LEGACY_DOMAIN at all, even if both constants are ever renamed or
    removed (e.g. a future HA Core submission dropping the "_ce" suffix).
    """
    monkeypatch.setattr(coordinator_module, "DOMAIN", "something_else_entirely")
    monkeypatch.setattr(coordinator_module, "LEGACY_DOMAIN", "unrelated")
    assert _is_truenas_sensor_id("sensor.truenas_cpu_usage", "truenas") is True


def test_is_truenas_sensor_id_scoped_to_this_entrys_device_slug() -> None:
    """Regression (#61): a global slug match flagged every entry's orphans.

    That happened on multi-entry installs. Each entry must only match its
    own device slug.
    """
    assert (
        _is_truenas_sensor_id("sensor.truenas_nuc13_cpu_usage", "truenas_nuc13") is True
    )
    assert (
        _is_truenas_sensor_id("sensor.truenas_x11dpu_cpu_usage", "truenas_nuc13")
        is False
    )


def test_is_truenas_sensor_id_rejects_empty_device_slug() -> None:
    """An empty slug (e.g. a blank device name) must never match every id."""
    assert _is_truenas_sensor_id("sensor.truenas_nuc13_cpu_usage", "") is False


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
#   _apply_pool_capacity
# ---------------------------
def test_apply_pool_capacity_uses_root_dataset_when_available() -> None:
    """Pool capacity is computed from the root dataset when one is provided."""
    coord = _bare_coordinator()
    coord.ds = {"pool": {"p1": {}}}
    root_dataset = {"available": 40, "used": 60}
    coord._apply_pool_capacity("p1", {}, root_dataset)
    assert coord.ds["pool"]["p1"]["available"] == 40
    assert coord.ds["pool"]["p1"]["total"] == 100
    assert coord.ds["pool"]["p1"]["usage"] == 60


def test_apply_pool_capacity_falls_back_to_pool_fields_without_root_dataset() -> None:
    """Without a root dataset, capacity falls back to the pool's own free/size fields."""
    coord = _bare_coordinator()
    coord.ds = {"pool": {"p1": {}}}
    vals = {"free": 30, "size": 100}
    coord._apply_pool_capacity("p1", vals, None)
    assert coord.ds["pool"]["p1"]["available"] == 30
    assert coord.ds["pool"]["p1"]["total"] == 100
    assert coord.ds["pool"]["p1"]["usage"] == 70


def test_apply_pool_capacity_zero_total_yields_zero_usage() -> None:
    """A zero-sized pool reports zero usage instead of dividing by zero."""
    coord = _bare_coordinator()
    coord.ds = {"pool": {"p1": {}}}
    coord._apply_pool_capacity("p1", {"free": 0, "size": 0, "allocated": 0}, None)
    assert coord.ds["pool"]["p1"]["usage"] == 0


# ---------------------------
#   _apply_pool_errors
# ---------------------------
def test_apply_pool_errors_aggregates_into_matching_pool() -> None:
    """Vdev error counts from a matching-guid raw pool are aggregated in."""
    coord = _bare_coordinator()
    coord.ds = {"pool": {"guid1": {}}}
    raw_pools = [
        {
            "guid": "guid1",
            "topology": {
                "data": [
                    {
                        "stats": {
                            "read_errors": 1,
                            "write_errors": 2,
                            "checksum_errors": 3,
                        }
                    }
                ]
            },
        }
    ]
    coord._apply_pool_errors(raw_pools)
    pool = coord.ds["pool"]["guid1"]
    assert (pool["read_errors"], pool["write_errors"], pool["checksum_errors"]) == (
        1,
        2,
        3,
    )
    assert pool["errors"] == 6


def test_apply_pool_errors_skips_unknown_guid_and_non_dict_entries() -> None:
    """Entries with an unknown guid or a non-dict shape are skipped."""
    coord = _bare_coordinator()
    coord.ds = {"pool": {"guid1": {}}}
    coord._apply_pool_errors([{"guid": "unknown-guid", "topology": {}}, "not-a-dict"])
    assert coord.ds["pool"]["guid1"] == {}


def test_apply_pool_errors_noop_for_non_list_input() -> None:
    """A non-list raw_pools argument leaves the pool data untouched."""
    coord = _bare_coordinator()
    coord.ds = {"pool": {"guid1": {}}}
    coord._apply_pool_errors(None)
    assert coord.ds["pool"]["guid1"] == {}


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
#   _rollback_possible / issue-id builders
# ---------------------------
def test_rollback_possible_false_when_domain_is_legacy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rollback is impossible once the integration is already running as legacy."""
    coord = _bare_coordinator()
    monkeypatch.setattr(coordinator_module, "DOMAIN", LEGACY_DOMAIN)
    assert coord._rollback_possible() is False


def test_rollback_possible_true_when_legacy_entry_exists() -> None:
    """Rollback is possible when a recorded legacy entry id still resolves."""
    coord = _bare_coordinator()
    coord.config_entry = MagicMock()
    coord.config_entry.data = {MIGRATION_LEGACY_ENTRY_ID: "legacy-id-1"}
    coord.hass = MagicMock()
    coord.hass.config_entries.async_get_entry.return_value = MagicMock()
    assert coord._rollback_possible() is True


def test_rollback_possible_false_when_no_legacy_id_recorded() -> None:
    """Rollback is impossible when no legacy entry id was ever recorded."""
    coord = _bare_coordinator()
    coord.config_entry = MagicMock()
    coord.config_entry.data = {}
    coord.hass = MagicMock()
    assert coord._rollback_possible() is False


def test_statistics_issue_id_includes_entry_id() -> None:
    """The orphaned-statistics issue id is scoped by config entry id."""
    coord = _bare_coordinator()
    coord.config_entry = MagicMock()
    coord.config_entry.entry_id = "entry123"
    assert coord._statistics_issue_id() == "statistics_orphaned_entry123"


def test_migration_rollback_issue_id_includes_entry_id() -> None:
    """The migration-rollback issue id is scoped by config entry id."""
    coord = _bare_coordinator()
    coord.config_entry = MagicMock()
    coord.config_entry.entry_id = "entry123"
    assert (
        coord._migration_rollback_issue_id() == "migration_rollback_available_entry123"
    )


# ---------------------------
#   get_alerts
# ---------------------------
async def test_get_alerts_malformed_response_resets_to_defaults() -> None:
    """A non-list alerts response resets the alerts dict to its defaults."""
    coord = _bare_coordinator()
    coord.ds = {"alerts": {}}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value={"not": "a list"})
    await coord.get_alerts()
    assert coord.ds["alerts"] == {
        "count": 0,
        "messages": [],
        "critical": 0,
        "warning": 0,
        "info": 0,
        "disk_issues": False,
    }


async def test_get_alerts_filters_dismissed_and_counts_levels() -> None:
    """Dismissed alerts are excluded and remaining alerts are counted per level."""
    coord = _bare_coordinator()
    coord.ds = {"alerts": {}}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(
        return_value=[
            {
                "dismissed": True,
                "level": "CRITICAL",
                "klass": "disk",
                "formatted": "ignored",
            },
            {
                "dismissed": False,
                "level": "CRITICAL",
                "klass": "PoolUsage",
                "formatted": "Pool full",
                "uuid": "u1",
            },
            {
                "dismissed": False,
                "level": "WARNING",
                "klass": "Other",
                "title": "SMART failure",
                "formatted": "Smart warning",
                "uuid": "u2",
            },
            {
                "dismissed": False,
                "level": "INFO",
                "klass": "Other",
                "title": "",
                "formatted": "Just info",
            },
        ]
    )
    await coord.get_alerts()
    alerts = coord.ds["alerts"]
    assert alerts["count"] == 3
    assert alerts["critical"] == 1
    assert alerts["warning"] == 1
    assert alerts["info"] == 1
    assert alerts["disk_issues"] is True
    assert alerts["messages"] == ["Pool full", "Smart warning", "Just info"]
    assert alerts["uuids"] == ["u1", "u2"]


async def test_get_alerts_no_disk_issues_when_unrelated() -> None:
    """An alert from an unrelated class does not set the disk_issues flag."""
    coord = _bare_coordinator()
    coord.ds = {"alerts": {}}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(
        return_value=[
            {
                "dismissed": False,
                "level": "INFO",
                "klass": "CertificateExpiry",
                "title": "cert",
                "formatted": "Cert expiring",
            }
        ]
    )
    await coord.get_alerts()
    assert coord.ds["alerts"]["disk_issues"] is False


# ---------------------------
#   get_smb
# ---------------------------
async def test_get_smb_counts_list_response() -> None:
    """A list SMB response's length becomes the connection count."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {}}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value=[{"id": 1}, {"id": 2}])
    await coord.get_smb()
    assert coord.ds["system_info"]["smb_connections"] == 2


async def test_get_smb_counts_dict_with_sessions() -> None:
    """A dict SMB response's "sessions" list length becomes the connection count."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {}}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value={"sessions": [{}, {}, {}]})
    await coord.get_smb()
    assert coord.ds["system_info"]["smb_connections"] == 3


async def test_get_smb_defaults_to_zero_for_unexpected_shape() -> None:
    """An unexpected (non-list, non-dict) SMB response defaults the count to zero."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {}}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value=None)
    await coord.get_smb()
    assert coord.ds["system_info"]["smb_connections"] == 0


# ---------------------------
#   get_updatecheck
# ---------------------------
async def test_get_updatecheck_malformed_response_resets_idle() -> None:
    """A non-dict update-check response resets to no-update-available."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {"version": "25.04.1"}}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value="not-a-dict")
    await coord.get_updatecheck()
    info = coord.ds["system_info"]
    assert info["update_available"] is False
    assert info["update_version"] == "25.04.1"


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


async def test_get_updatecheck_empty_response_resets_status() -> None:
    """An empty update-check response resets the update status."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {"version": "25.04.1"}}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value={})
    await coord.get_updatecheck()
    info = coord.ds["system_info"]
    assert info["update_available"] is False
    assert info["update_version"] == "25.04.1"


async def test_get_updatecheck_new_version_available() -> None:
    """An AVAILABLE update-check response populates the new-version fields."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {"version": "25.04.1"}}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(
        return_value={
            "status": {
                "state": "AVAILABLE",
                "new_version": {
                    "version": "25.10.0",
                    "manifest": {
                        "date": "2026-01-01",
                        "profile": "stable",
                        "train": "SCALE",
                        "filename": "update.pkg",
                    },
                },
            }
        }
    )
    await coord.get_updatecheck()
    info = coord.ds["system_info"]
    assert info["update_available"] is True
    assert info["update_version"] == "25.10.0"
    assert info["update_state"] == "AVAILABLE"
    assert info["update_date"] == "2026-01-01"
    assert info["update_train"] == "SCALE"


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


async def test_get_updatecheck_no_new_version_resets_status() -> None:
    """An IDLE state with no new_version resets update_available to False."""
    coord = _bare_coordinator()
    coord.ds = {"system_info": {"version": "25.04.1", "update_available": True}}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(
        return_value={"status": {"state": "IDLE", "new_version": None}}
    )
    await coord.get_updatecheck()
    info = coord.ds["system_info"]
    assert info["update_available"] is False
    assert info["update_version"] == "25.04.1"


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


async def test_async_ensure_connected_raises_auth_failed_on_invalid_key() -> None:
    """An ERR_INVALID_KEY connect failure is translated into ConfigEntryAuthFailed."""
    coord = _bare_coordinator()
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=False)
    coord.api.connect = AsyncMock(return_value=False)
    coord.api.error = "ERR_INVALID_KEY"
    coord.host = "truenas.local"
    with (
        patch.object(coordinator_module, "ERR_INVALID_KEY", "ERR_INVALID_KEY"),
        pytest.raises(coordinator_module.ConfigEntryAuthFailed),
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
        "get_service",
        "get_disk",
        "get_dataset",
        "get_vm",
        "get_container",
        "get_directoryservices",
        "get_cloudsync",
        "get_replication",
        "get_rsync",
        "get_snapshottask",
        "get_scrub",
        "get_app",
        "get_app_stats",
        "get_cronjob",
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
    coord.async_detect_orphaned_statistics = AsyncMock()
    coord._clear_stale_migration_rollback_issue = MagicMock()
    coord.last_updatecheck_update = datetime(1970, 1, 1, tzinfo=UTC)
    _stub_all_jobs(coord)
    coord.ds = {"foo": "bar"}

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
    coord.async_detect_orphaned_statistics = AsyncMock()
    coord._clear_stale_migration_rollback_issue = MagicMock()
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
    coord.async_detect_orphaned_statistics = AsyncMock()
    coord._clear_stale_migration_rollback_issue = MagicMock()
    coord.last_updatecheck_update = dt_util.utcnow()
    _stub_all_jobs(coord)
    coord.get_service = AsyncMock(side_effect=Exception("boom"))
    coord.ds = {}

    result = await coord._async_update_data()  # must not raise

    assert result is coord.ds


# ---------------------------
#   Orphaned statistics / migration rollback lifecycle
# ---------------------------
async def test_async_detect_orphaned_statistics_skips_without_recorder() -> None:
    """Without the recorder component loaded, no orphan detection is attempted."""
    coord = _bare_coordinator()
    coord.hass = MagicMock()
    coord.hass.config.components = set()
    await coord.async_detect_orphaned_statistics()
    assert coord.orphaned_statistics == []


async def test_async_detect_orphaned_statistics_handles_listing_exception() -> None:
    """An exception while listing statistics is swallowed, leaving no orphans."""
    coord = _bare_coordinator()
    coord.hass = MagicMock()
    coord.hass.config.components = {"recorder"}
    with patch.object(
        coordinator_module,
        "get_instance",
        return_value=MagicMock(
            async_add_executor_job=AsyncMock(side_effect=Exception("boom"))
        ),
    ):
        await coord.async_detect_orphaned_statistics()
    assert coord.orphaned_statistics == []


async def test_async_detect_orphaned_statistics_filters_matching_ids() -> None:
    """Matching ids are kept, everything else dropped — and the result is sorted."""
    coord = _bare_coordinator()
    coord.hass = MagicMock()
    coord.hass.config.components = {"recorder"}
    coord.config_entry = MagicMock()
    coord.config_entry.entry_id = "entry1"
    coord.config_entry.options = {}
    slug = slugify(DEFAULT_DEVICE_NAME)
    coord._device_slug = slug
    stat_ids = [
        {"statistic_id": f"sensor.{slug}_cpu_usage", "source": "recorder"},
        {"statistic_id": f"sensor.{slug}_arc_size", "source": "recorder"},
        {"statistic_id": "sensor.unrelated_thing", "source": "recorder"},
        "not-a-dict",
    ]
    ent_reg = MagicMock()
    ent_reg.async_get.return_value = None
    with (
        patch.object(
            coordinator_module,
            "get_instance",
            return_value=MagicMock(
                async_add_executor_job=AsyncMock(return_value=stat_ids)
            ),
        ),
        patch.object(coordinator_module.er, "async_get", return_value=ent_reg),
        patch.object(coordinator_module.ir, "async_create_issue") as create_mock,
    ):
        await coord.async_detect_orphaned_statistics()

    assert coord.orphaned_statistics == [
        f"sensor.{slug}_arc_size",
        f"sensor.{slug}_cpu_usage",
    ]
    create_mock.assert_called_once()


async def test_async_detect_orphaned_statistics_ignores_other_entrys_device() -> None:
    """Regression (#61): with two TrueNAS config entries, detection used to match a fixed global slug.

    So each entry's coordinator flagged the *other* entry's orphaned
    statistics too and both raised their own duplicate Repairs issue for the
    same global list. Each entry must only see statistics whose id matches
    its own device-name slug.
    """
    coord = _bare_coordinator()
    coord.hass = MagicMock()
    coord.hass.config.components = {"recorder"}
    coord.config_entry = MagicMock()
    coord.config_entry.entry_id = "entry1"
    coord.config_entry.options = {}
    coord._device_slug = slugify("TrueNAS nuc13")
    stat_ids = [
        {
            "statistic_id": "sensor.truenas_nuc13_certificates_cert_time_until_expiry",
            "source": "recorder",
        },
        {
            "statistic_id": "sensor.truenas_x11dpu_certificates_cert_time_until_expiry",
            "source": "recorder",
        },
    ]
    ent_reg = MagicMock()
    ent_reg.async_get.return_value = None
    with (
        patch.object(
            coordinator_module,
            "get_instance",
            return_value=MagicMock(
                async_add_executor_job=AsyncMock(return_value=stat_ids)
            ),
        ),
        patch.object(coordinator_module.er, "async_get", return_value=ent_reg),
        patch.object(coordinator_module.ir, "async_create_issue"),
    ):
        await coord.async_detect_orphaned_statistics()

    assert coord.orphaned_statistics == [
        "sensor.truenas_nuc13_certificates_cert_time_until_expiry"
    ]


async def test_async_detect_orphaned_statistics_logs_ids_on_change(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The full id list is logged once per change, not on every poll."""
    coord = _bare_coordinator()
    coord.hass = MagicMock()
    coord.hass.config.components = {"recorder"}
    coord.config_entry = MagicMock()
    coord.config_entry.entry_id = "entry1"
    coord.config_entry.options = {}
    slug = slugify(DEFAULT_DEVICE_NAME)
    coord._device_slug = slug
    stat_ids = [{"statistic_id": f"sensor.{slug}_cpu_usage", "source": "recorder"}]
    ent_reg = MagicMock()
    ent_reg.async_get.return_value = None
    with (
        patch.object(
            coordinator_module,
            "get_instance",
            return_value=MagicMock(
                async_add_executor_job=AsyncMock(return_value=stat_ids)
            ),
        ),
        patch.object(coordinator_module.er, "async_get", return_value=ent_reg),
        patch.object(coordinator_module.ir, "async_create_issue"),
        caplog.at_level("DEBUG", logger=coordinator_module.__name__),
    ):
        await coord.async_detect_orphaned_statistics()
        assert f"sensor.{slug}_cpu_usage" in caplog.text

        caplog.clear()
        await coord.async_detect_orphaned_statistics()

    assert "Orphaned TrueNAS statistics" not in caplog.text


def test_count_statistics_with_data_counts_only_ids_with_rows() -> None:
    """Only statistic ids whose lookup returns rows are counted."""
    hass = MagicMock()
    with patch.object(
        coordinator_module,
        "get_last_statistics",
        side_effect=[{"sensor.a": [{"state": 1}]}, {}],
    ) as stats_mock:
        assert _count_statistics_with_data(hass, ["sensor.a", "sensor.b"]) == 1

    # Pinned on purpose: ``get_last_statistics`` takes a single id as a bare
    # ``str`` and builds ``{statistic_id}`` from it internally. Wrapping it in a
    # list would raise "unhashable type: 'list'", so this asserts the id is
    # never "helpfully" turned into a sequence.
    assert [call.args[2] for call in stats_mock.call_args_list] == [
        "sensor.a",
        "sensor.b",
    ]


async def test_async_count_orphans_with_data_returns_zero_without_orphans() -> None:
    """With no orphaned statistics recorded, the count is zero without probing."""
    coord = _bare_coordinator()
    coord.hass = MagicMock()
    coord.orphaned_statistics = []
    assert await coord.async_count_orphans_with_data() == 0


async def test_async_count_orphans_with_data_probes_recorder() -> None:
    """With the recorder loaded, the count comes from probing actual statistics."""
    coord = _bare_coordinator()
    coord.hass = MagicMock()
    coord.hass.config.components = {"recorder"}
    coord.orphaned_statistics = ["sensor.truenas_a", "sensor.truenas_b"]
    with patch.object(
        coordinator_module,
        "get_instance",
        return_value=MagicMock(async_add_executor_job=AsyncMock(return_value=1)),
    ):
        assert await coord.async_count_orphans_with_data() == 1


async def test_async_count_orphans_with_data_assumes_all_without_recorder() -> None:
    """Without the recorder loaded the probe cannot run: assume the worst case."""
    coord = _bare_coordinator()
    coord.hass = MagicMock()
    coord.hass.config.components = set()
    coord.orphaned_statistics = ["sensor.truenas_a"]
    assert await coord.async_count_orphans_with_data() == 1


async def test_async_count_orphans_with_data_falls_back_on_error() -> None:
    """A probing error assumes every recorded orphan still has data."""
    coord = _bare_coordinator()
    coord.hass = MagicMock()
    coord.hass.config.components = {"recorder"}
    coord.orphaned_statistics = ["sensor.truenas_a", "sensor.truenas_b"]
    with patch.object(
        coordinator_module,
        "get_instance",
        return_value=MagicMock(
            async_add_executor_job=AsyncMock(side_effect=Exception("boom"))
        ),
    ):
        assert await coord.async_count_orphans_with_data() == 2


def test_update_statistics_issue_deletes_when_no_orphans() -> None:
    """No orphaned statistics deletes any existing Repairs issue."""
    coord = _bare_coordinator()
    coord.hass = MagicMock()
    coord.config_entry = MagicMock()
    coord.config_entry.entry_id = "entry1"
    coord.config_entry.options = {}
    coord.orphaned_statistics = []
    with patch.object(coordinator_module.ir, "async_delete_issue") as delete_mock:
        coord._update_statistics_issue()
    delete_mock.assert_called_once()


def test_update_statistics_issue_skips_creation_when_ignored() -> None:
    """An ignored statistics-cleanup option skips (re-)creating the issue."""
    coord = _bare_coordinator()
    coord.hass = MagicMock()
    coord.config_entry = MagicMock()
    coord.config_entry.entry_id = "entry1"
    coord.config_entry.options = {CONF_STATISTICS_CLEANUP_IGNORED: True}
    coord.orphaned_statistics = ["sensor.truenas_x"]
    with patch.object(coordinator_module.ir, "async_delete_issue") as delete_mock:
        coord._update_statistics_issue()
    delete_mock.assert_called_once()


def test_raise_migration_rollback_issue_noop_when_not_possible() -> None:
    """No rollback-eligible legacy entry means no issue is created."""
    coord = _bare_coordinator()
    coord.config_entry = MagicMock()
    coord.config_entry.data = {}
    coord.hass = MagicMock()
    with patch.object(coordinator_module.ir, "async_create_issue") as create_mock:
        coord.raise_migration_rollback_issue()
    create_mock.assert_not_called()


def test_raise_migration_rollback_issue_creates_when_possible() -> None:
    """A rollback-eligible legacy entry causes the Repairs issue to be created."""
    coord = _bare_coordinator()
    coord.config_entry = MagicMock()
    coord.config_entry.entry_id = "entry1"
    coord.config_entry.data = {
        MIGRATION_LEGACY_ENTRY_ID: "legacy-1",
        MIGRATION_RECORDS: [1, 2],
    }
    coord.hass = MagicMock()
    coord.hass.config_entries.async_get_entry.return_value = MagicMock()
    with patch.object(coordinator_module.ir, "async_create_issue") as create_mock:
        coord.raise_migration_rollback_issue()
    create_mock.assert_called_once()


def test_clear_stale_migration_rollback_issue_inert_for_legacy_domain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Running as the legacy domain never deletes the migration-rollback issue."""
    monkeypatch.setattr(coordinator_module, "DOMAIN", LEGACY_DOMAIN)
    coord = _bare_coordinator()
    with patch.object(coordinator_module.ir, "async_delete_issue") as delete_mock:
        coord._clear_stale_migration_rollback_issue()
    delete_mock.assert_not_called()


def test_clear_stale_migration_rollback_issue_deletes_when_rollback_impossible() -> (
    None
):
    """Once rollback is no longer possible, any stale issue is deleted."""
    coord = _bare_coordinator()
    coord.config_entry = MagicMock()
    coord.config_entry.entry_id = "entry1"
    coord.config_entry.data = {}
    coord.hass = MagicMock()
    with patch.object(coordinator_module.ir, "async_delete_issue") as delete_mock:
        coord._clear_stale_migration_rollback_issue()
    delete_mock.assert_called_once()


async def test_async_clear_orphaned_statistics_noop_when_empty() -> None:
    """No orphaned statistics means the clear routine does nothing."""
    coord = _bare_coordinator()
    coord.orphaned_statistics = []
    coord.hass = MagicMock()
    await coord.async_clear_orphaned_statistics()
    coord.hass.assert_not_called() if callable(coord.hass) else None


async def test_async_clear_orphaned_statistics_clears_and_refreshes() -> None:
    """Orphaned statistics are cleared, the issue deleted, and listeners refreshed."""
    coord = _bare_coordinator()
    coord.orphaned_statistics = ["sensor.truenas_x"]
    coord.hass = MagicMock()
    coord.config_entry = MagicMock()
    coord.config_entry.entry_id = "entry1"
    coord.ds = {"foo": "bar"}
    coord.async_set_updated_data = MagicMock()
    instance_mock = MagicMock()
    instance_mock.async_clear_statistics = MagicMock()
    with (
        patch.object(coordinator_module, "get_instance", return_value=instance_mock),
        patch.object(coordinator_module.ir, "async_delete_issue") as delete_mock,
    ):
        await coord.async_clear_orphaned_statistics()

    instance_mock.async_clear_statistics.assert_called_once_with(["sensor.truenas_x"])
    assert coord.orphaned_statistics == []
    delete_mock.assert_called_once()
    coord.async_set_updated_data.assert_called_once_with(coord.ds)


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
async def test_get_service_derives_running_and_display_name() -> None:
    """A service's running flag and display name are derived from raw fields."""
    coord = _bare_coordinator()
    coord.ds = {"service": {}}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(
        return_value=[
            {
                "id": 1,
                "service": "cifs",
                "name": "",
                "enable": True,
                "state": "RUNNING",
            },
            {
                "id": 2,
                "service": "ssh",
                "name": "Custom SSH",
                "enable": False,
                "state": "STOPPED",
            },
        ]
    )
    await coord.get_service()
    assert coord.ds["service"][1]["running"] is True
    assert coord.ds["service"][1]["display_name"] == "SMB"
    assert coord.ds["service"][2]["display_name"] == "Custom SSH"


# ---------------------------
#   get_pool / _add_boot_pool
# ---------------------------
async def test_get_pool_uses_dataset_mountpoint_match() -> None:
    """A pool's capacity is taken from the dataset matching its mountpoint."""
    coord = _bare_coordinator()
    coord.ds = {
        "pool": {},
        "dataset": {"tank": {"mountpoint": "/mnt/tank", "available": 40, "used": 60}},
    }
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.query = AsyncMock(
        side_effect=[
            [
                {
                    "guid": "g1",
                    "name": "tank",
                    "path": "/mnt/tank",
                    "fragmentation": "12",
                    "topology": {},
                }
            ],
            None,  # boot.get_state
        ]
    )
    await coord.get_pool()
    assert coord.ds["pool"]["g1"]["available"] == 40
    assert coord.ds["pool"]["g1"]["total"] == 100
    assert coord.ds["pool"]["g1"]["fragmentation"] == 12


async def test_get_pool_falls_back_to_name_match_when_no_mountpoint() -> None:
    """Without a mountpoint match, the pool falls back to matching by dataset id."""
    coord = _bare_coordinator()
    coord.ds = {
        "pool": {},
        # mountpoint "unknown" is excluded from the mountpoint lookup, forcing
        # the fallback match by dataset id == pool name.
        "dataset": {"tank": {"mountpoint": "unknown", "available": 40, "used": 60}},
    }
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.query = AsyncMock(
        side_effect=[
            [
                {
                    "guid": "g1",
                    "name": "tank",
                    "path": "/mnt/tank",
                    "fragmentation": "12",
                    "topology": {},
                }
            ],
            None,  # boot.get_state
        ]
    )
    await coord.get_pool()
    assert coord.ds["pool"]["g1"]["available"] == 40
    assert coord.ds["pool"]["g1"]["total"] == 100


async def test_get_pool_returns_early_when_disconnected() -> None:
    """A disconnected API leaves the pool dict empty instead of raising."""
    coord = _bare_coordinator()
    coord.ds = {"pool": {}, "dataset": {}}
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=False)
    coord.api.query = AsyncMock(return_value=[])
    await coord.get_pool()
    assert coord.ds["pool"] == {}


async def test_add_boot_pool_adds_when_present() -> None:
    """A present boot pool is added to the pool dict."""
    coord = _bare_coordinator()
    coord.ds = {"pool": {}}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(
        return_value={"name": "boot-pool", "topology": {}, "fragmentation": "0"}
    )
    await coord._add_boot_pool()
    assert "boot-pool" in coord.ds["pool"]


async def test_add_boot_pool_noop_when_absent() -> None:
    """A None boot-pool response leaves the pool dict empty."""
    coord = _bare_coordinator()
    coord.ds = {"pool": {}}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value=None)
    await coord._add_boot_pool()
    assert coord.ds["pool"] == {}


# ---------------------------
#   get_dataset
# ---------------------------
async def test_get_dataset_empty_when_group_not_monitored() -> None:
    """An unmonitored datasets group clears the dict without querying the API."""
    coord = _bare_coordinator()
    coord.ds = {"dataset": {"stale": {}}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: []}
    coord.api = MagicMock()
    coord.api.query = AsyncMock()
    await coord.get_dataset()
    assert coord.ds["dataset"] == {}
    coord.api.query.assert_not_awaited()


async def test_get_dataset_returns_early_when_no_datasets_found() -> None:
    """An empty datasets response leaves the dataset dict empty."""
    coord = _bare_coordinator()
    coord.ds = {"dataset": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: [MONITOR_GROUP_DATASETS]}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value=[])
    await coord.get_dataset()
    assert coord.ds["dataset"] == {}


async def test_get_dataset_parses_when_monitored() -> None:
    """A monitored datasets group parses the API response into the dataset dict."""
    coord = _bare_coordinator()
    coord.ds = {"dataset": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: [MONITOR_GROUP_DATASETS]}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(
        return_value=[{"id": "tank", "type": "FILESYSTEM", "name": "tank"}]
    )
    await coord.get_dataset()
    assert "tank" in coord.ds["dataset"]


async def test_update_disk_temperatures_applies_netdata_and_falls_back() -> None:
    """Disks with netdata readings use them; disks without fall back to SMART."""
    coord = _bare_coordinator()
    coord.ds = {"disk": {"d1": {"temperature": 40}, "d2": {"temperature": None}}}
    coord._disk_temps_from_netdata = AsyncMock(return_value={"sda": 40.0})
    coord._build_disk_name_map = MagicMock(return_value={"sda": "d1"})
    coord._apply_netdata_temps = MagicMock()
    coord._fallback_disk_temperatures = AsyncMock()

    await coord._update_disk_temperatures()

    coord._build_disk_name_map.assert_called_once()
    coord._apply_netdata_temps.assert_called_once_with({"sda": 40.0}, {"sda": "d1"})
    coord._fallback_disk_temperatures.assert_awaited_once_with(["d2"], True)


async def test_update_disk_temperatures_falls_back_for_all_without_netdata() -> None:
    """With no netdata readings, every disk falls back to the SMART lookup."""
    coord = _bare_coordinator()
    coord.ds = {"disk": {"d1": {"temperature": 40}, "d2": {"temperature": None}}}
    coord._disk_temps_from_netdata = AsyncMock(return_value=None)
    coord._build_disk_name_map = MagicMock()
    coord._apply_netdata_temps = MagicMock()
    coord._fallback_disk_temperatures = AsyncMock()

    await coord._update_disk_temperatures()

    coord._build_disk_name_map.assert_not_called()
    coord._apply_netdata_temps.assert_not_called()
    coord._fallback_disk_temperatures.assert_awaited_once()
    fallback_uids = coord._fallback_disk_temperatures.call_args.args[0]
    assert set(fallback_uids) == {"d1", "d2"}
    assert coord._fallback_disk_temperatures.call_args.args[1] is False


# ---------------------------
#   get_disk and disk-temperature helpers
# ---------------------------
async def test_get_disk_populates_and_updates_temperatures() -> None:
    """get_disk populates the disk dict and triggers a temperature update."""
    coord = _bare_coordinator()
    coord.ds = {"disk": {}}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(
        return_value=[
            {"identifier": "disk1", "devname": "sda", "name": "sda", "type": "HDD"}
        ]
    )
    coord._update_disk_temperatures = AsyncMock()
    await coord.get_disk()
    assert "disk1" in coord.ds["disk"]
    coord._update_disk_temperatures.assert_awaited_once()


def test_build_disk_name_map_collects_all_keys() -> None:
    """The disk name map indexes each disk by both identifier and devname."""
    coord = _bare_coordinator()
    coord.ds = {
        "disk": {"d1": {"identifier": "disk1", "devname": "sda", "name": "sda"}}
    }
    disk_map = coord._build_disk_name_map()
    assert disk_map == {"disk1": "d1", "sda": "d1"}


def test_build_disk_name_map_logs_collision(caplog: pytest.LogCaptureFixture) -> None:
    """Two disks sharing the same identifier log a collision warning."""
    coord = _bare_coordinator()
    coord.ds = {
        "disk": {
            "d1": {"identifier": "shared", "devname": "sda", "name": "sda"},
            "d2": {"identifier": "shared", "devname": "sdb", "name": "sdb"},
        }
    }
    with caplog.at_level("DEBUG"):
        coord._build_disk_name_map()
    assert "collision" in caplog.text


def test_apply_netdata_temps_matches_by_disk_map() -> None:
    """A netdata reading is applied to the disk resolved through the name map."""
    coord = _bare_coordinator()
    coord.ds = {"disk": {"d1": {"temperature": None}}}
    coord._apply_netdata_temps({"sda": 42.345}, {"sda": "d1"})
    # 42.345 isn't exactly representable as a float, so round() gives 42.34.
    assert coord.ds["disk"]["d1"]["temperature"] == round(42.345, 2)


async def test_fallback_disk_temperatures_maps_matched_disk() -> None:
    """A SMART temperature keyed by devname is applied to the matching disk."""
    coord = _bare_coordinator()
    coord.ds = {
        "disk": {"d1": {"name": "sda", "devname": "sda", "identifier": "disk1"}}
    }
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value={"sda": 39.0})
    await coord._fallback_disk_temperatures(["d1"], has_netdata=False)
    assert coord.ds["disk"]["d1"]["temperature"] == 39.0


async def test_fallback_disk_temperatures_warns_on_invalid_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A None SMART temperature response logs a warning about the failed update."""
    coord = _bare_coordinator()
    coord.ds = {
        "disk": {"d1": {"name": "sda", "devname": "sda", "identifier": "disk1"}}
    }
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value=None)
    with caplog.at_level("WARNING"):
        await coord._fallback_disk_temperatures(["d1"], has_netdata=False)
    assert "Failed to update disk temperatures" in caplog.text


def test_map_single_disk_api_temp_sets_matched_value() -> None:
    """A matching temperature entry is written to the disk's temperature field."""
    coord = _bare_coordinator()
    coord.ds = {
        "disk": {"d1": {"name": "sda", "devname": "sda", "identifier": "disk1"}}
    }
    coord._map_single_disk_api_temp("d1", {"sda": 41.5})
    assert coord.ds["disk"]["d1"]["temperature"] == 41.5


def test_map_single_disk_api_temp_logs_when_no_match(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No matching temperature entry logs a debug message instead of raising."""
    coord = _bare_coordinator()
    coord.ds = {
        "disk": {"d1": {"name": "sda", "devname": "sda", "identifier": "disk1"}}
    }
    with caplog.at_level("DEBUG"):
        coord._map_single_disk_api_temp("d1", {"other": 41.5})
    assert "No matching temperature entry" in caplog.text


def test_map_single_disk_api_temp_logs_invalid_value(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A non-numeric temperature value logs a debug message instead of raising."""
    coord = _bare_coordinator()
    coord.ds = {
        "disk": {"d1": {"name": "sda", "devname": "sda", "identifier": "disk1"}}
    }
    with caplog.at_level("DEBUG"):
        coord._map_single_disk_api_temp("d1", {"sda": "not-a-number"})
    assert "Invalid temperature value" in caplog.text


async def test_disk_temps_from_netdata_returns_none_without_graph() -> None:
    """No discoverable disk-temp graph name yields None."""
    coord = _bare_coordinator()
    coord._disk_temp_graph = None
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value=None)
    coord._discover_disk_temp_graph = AsyncMock(return_value="")
    assert await coord._disk_temps_from_netdata() is None


async def test_disk_temps_from_netdata_returns_none_on_invalid_graph_data() -> None:
    """A None graph-data response yields None."""
    coord = _bare_coordinator()
    coord._disk_temp_graph = "disk_temp"
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value=None)
    assert await coord._disk_temps_from_netdata() is None


async def test_disk_temps_from_netdata_collects_temps() -> None:
    """Valid graph data yields a dict of per-disk temperatures."""
    coord = _bare_coordinator()
    coord._disk_temp_graph = "disk_temp"
    coord.api = MagicMock()
    coord.api.query = AsyncMock(
        return_value=[{"identifier": "disk1", "aggregations": {"mean": {"a": 35.0}}}]
    )
    result = await coord._disk_temps_from_netdata()
    assert result == {"disk1": 35.0}


async def test_discover_disk_temp_graph_finds_matching_name() -> None:
    """A graph whose title contains "Disk Temperature" is discovered by name."""
    coord = _bare_coordinator()
    coord.api = MagicMock()
    coord.api.query = AsyncMock(
        return_value=[{"name": "disk_temp_sda", "title": "Disk Temperature"}]
    )
    result = await coord._discover_disk_temp_graph()
    assert result == "disk_temp_sda"


async def test_discover_disk_temp_graph_returns_empty_when_not_found() -> None:
    """A None graphs response yields an empty string."""
    coord = _bare_coordinator()
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value=None)
    assert await coord._discover_disk_temp_graph() == ""


async def test_discover_disk_temp_graph_returns_empty_when_no_match() -> None:
    """No graph title matching disk-temperature yields an empty string."""
    coord = _bare_coordinator()
    coord.api = MagicMock()
    coord.api.query = AsyncMock(
        return_value=[{"name": "cpu_load", "title": "CPU Load"}]
    )
    assert await coord._discover_disk_temp_graph() == ""


def test_collect_disk_temp_uses_median_of_valid_means() -> None:
    """Out-of-range mean values are discarded before taking the median."""
    coord = _bare_coordinator()
    temps: dict[str, float] = {}
    # 200.0 is outside the 0-100 sane bound and is discarded, leaving [30.0, 32.0]
    # whose median (even count) is their average, 31.0.
    coord._collect_disk_temp(
        {
            "identifier": "disk1",
            "aggregations": {"mean": {"a": 30.0, "b": 200.0, "c": 32.0}},
        },
        temps,
    )
    assert temps == {"disk1": 31.0}


def test_collect_disk_temp_ignores_entry_without_identifier() -> None:
    """An entry without an identifier is skipped, leaving temps unchanged."""
    coord = _bare_coordinator()
    temps: dict[str, float] = {}
    coord._collect_disk_temp({"aggregations": {"mean": {"a": 30.0}}}, temps)
    assert temps == {}


# ---------------------------
#   get_vm
# ---------------------------
async def test_get_vm_empty_when_not_monitored() -> None:
    """An unmonitored VMs group clears the dict without querying the API."""
    coord = _bare_coordinator()
    coord.ds = {"vm": {"stale": {}}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: []}
    coord.api = MagicMock()
    coord.api.query = AsyncMock()
    await coord.get_vm()
    assert coord.ds["vm"] == {}


async def test_get_vm_computes_memory_and_running() -> None:
    """A VM's memory is converted to GB and its running flag derived from status."""
    coord = _bare_coordinator()
    coord.ds = {"vm": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: [MONITOR_GROUP_VMS]}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(
        return_value=[
            {
                "id": 1,
                "name": "vm1",
                "vcpus": 2,
                "memory": 2048,
                "status": {"state": "RUNNING"},
            }
        ]
    )
    await coord.get_vm()
    assert coord.ds["vm"][1]["memory"] == 2
    assert coord.ds["vm"][1]["running"] is True


async def test_get_vm_handles_null_memory() -> None:
    """A None memory value normalizes to zero instead of raising."""
    coord = _bare_coordinator()
    coord.ds = {"vm": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: [MONITOR_GROUP_VMS]}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(
        return_value=[
            {
                "id": 1,
                "name": "vm1",
                "vcpus": 2,
                "memory": None,
                "status": {"state": "STOPPED"},
            }
        ]
    )
    await coord.get_vm()
    assert coord.ds["vm"][1]["memory"] == 0


# ---------------------------
#   get_container
# ---------------------------
async def test_get_container_filters_container_type_and_computes_fields() -> None:
    """Only CONTAINER-type entries are kept, with cpu/memory/running/ip derived."""
    coord = _bare_coordinator()
    coord.ds = {"container": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: [MONITOR_GROUP_CONTAINERS]}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(
        return_value=[
            {
                "id": "c1",
                "name": "app1",
                "type": "CONTAINER",
                "cpu": "1",
                "memory": 1048576,
                "status": "RUNNING",
                "aliases": [{"type": "INET", "address": "10.0.0.5"}],
            },
            {"id": "v1", "name": "legacyvm", "type": "VM"},
        ]
    )
    await coord.get_container()
    assert "c1" in coord.ds["container"]
    assert "v1" not in coord.ds["container"]
    assert coord.ds["container"]["c1"]["cpu"] == 1
    assert coord.ds["container"]["c1"]["memory"] == 1
    assert coord.ds["container"]["c1"]["running"] is True
    assert coord.ds["container"]["c1"]["ip_address"] == "10.0.0.5"


async def test_get_container_normalizes_non_numeric_memory() -> None:
    """A None memory value normalizes to zero instead of raising."""
    coord = _bare_coordinator()
    coord.ds = {"container": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: [MONITOR_GROUP_CONTAINERS]}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(
        return_value=[{"id": "c1", "name": "app1", "type": "CONTAINER", "memory": None}]
    )
    await coord.get_container()
    assert coord.ds["container"]["c1"]["memory"] == 0


async def test_get_container_empty_when_not_monitored() -> None:
    """An unmonitored containers group clears the dict without querying the API."""
    coord = _bare_coordinator()
    coord.ds = {"container": {"stale": {}}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: []}
    coord.api = MagicMock()
    coord.api.query = AsyncMock()
    await coord.get_container()
    assert coord.ds["container"] == {}


async def test_get_container_logs_when_query_returns_non_list(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A non-list query response logs a debug message and leaves the dict empty."""
    coord = _bare_coordinator()
    coord.ds = {"container": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: [MONITOR_GROUP_CONTAINERS]}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value=None)
    with caplog.at_level("DEBUG"):
        await coord.get_container()
    assert coord.ds["container"] == {}


# ---------------------------
#   get_directoryservices
# ---------------------------
async def test_get_directoryservices_empty_when_not_monitored() -> None:
    """An unmonitored directory-services group clears the dict without querying."""
    coord = _bare_coordinator()
    coord.ds = {"directoryservices": {"stale": {}}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: []}
    coord.api = MagicMock()
    coord.api.query = AsyncMock()
    await coord.get_directoryservices()
    assert coord.ds["directoryservices"] == {}


async def test_get_directoryservices_empty_when_not_configured() -> None:
    """A missing service_type leaves the directoryservices dict empty."""
    coord = _bare_coordinator()
    coord.ds = {"directoryservices": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {
        CONF_MONITORED_GROUPS: [MONITOR_GROUP_DIRECTORY_SERVICES]
    }
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value={"service_type": None})
    await coord.get_directoryservices()
    assert coord.ds["directoryservices"] == {}


async def test_get_directoryservices_populates_when_enabled() -> None:
    """A configured directory service's health status is populated."""
    coord = _bare_coordinator()
    coord.ds = {"directoryservices": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {
        CONF_MONITORED_GROUPS: [MONITOR_GROUP_DIRECTORY_SERVICES]
    }
    coord.api = MagicMock()
    coord.api.query = AsyncMock(
        side_effect=[
            {
                "id": 1,
                "service_type": "ACTIVEDIRECTORY",
                "enable": True,
                "enable_account_cache": True,
                "enable_dns_updates": True,
                "kerberos_realm": "REALM",
                "configuration": {"domain": "example.com", "site": "default"},
            },
            {"status": "HEALTHY", "status_msg": None},
        ]
    )
    await coord.get_directoryservices()
    assert coord.ds["directoryservices"][1]["healthy"] is True


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
async def test_get_arc_stores_none_for_missing_graph() -> None:
    """A None graph response leaves data_hit_percent as None."""
    coord = _bare_coordinator()
    coord.ds = {}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value=None)
    await coord.get_arc()
    assert coord.ds["arc"]["data_hit_percent"] is None


async def test_get_arc_computes_value_for_present_graph() -> None:
    """A present graph's mean value is stored as data_hit_percent."""
    coord = _bare_coordinator()
    coord.ds = {}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value=[{"aggregations": {"mean": {"a": 90.0}}}])
    await coord.get_arc()
    assert coord.ds["arc"]["data_hit_percent"] == 90.0


# ---------------------------
#   get_ups / _discover_ups_graphs
# ---------------------------
async def test_get_ups_empty_when_not_monitored() -> None:
    """An unmonitored UPS group clears the dict."""
    coord = _bare_coordinator()
    coord.ds = {"ups": {"stale": 1}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: []}
    coord._ups_graphs = None
    await coord.get_ups()
    assert coord.ds["ups"] == {}


async def test_get_ups_returns_when_discovery_fails() -> None:
    """A failed graph-discovery query leaves _ups_graphs as None."""
    coord = _bare_coordinator()
    coord.ds = {"ups": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: [MONITOR_GROUP_UPS]}
    coord._ups_graphs = None
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value=None)
    await coord.get_ups()
    assert coord._ups_graphs is None


async def test_get_ups_returns_when_no_graphs_discovered() -> None:
    """An empty set of previously discovered graphs skips the graph-data query."""
    coord = _bare_coordinator()
    coord.ds = {"ups": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: [MONITOR_GROUP_UPS]}
    coord._ups_graphs = set()
    coord.api = MagicMock()
    coord.api.query = AsyncMock()
    await coord.get_ups()
    coord.api.query.assert_not_awaited()


async def test_get_ups_assigns_discovered_graphs_when_previously_none() -> None:
    """Freshly discovered UPS graphs are cached and used to populate ups data."""
    coord = _bare_coordinator()
    coord.ds = {"ups": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: [MONITOR_GROUP_UPS]}
    coord._ups_graphs = None
    coord.api = MagicMock()
    coord.api.query = AsyncMock(
        side_effect=[
            [{"name": "upscharge"}],  # discovery call
            [{"aggregations": {"mean": {"a": 80.0}}}],  # graph data call
        ]
    )
    await coord.get_ups()
    assert coord._ups_graphs == {"upscharge"}
    assert coord.ds["ups"]["battery_charge"] == 80.0


async def test_get_ups_populates_known_graphs() -> None:
    """Previously discovered UPS graphs are used directly to populate ups data."""
    coord = _bare_coordinator()
    coord.ds = {"ups": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: [MONITOR_GROUP_UPS]}
    coord._ups_graphs = {"upscharge"}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value=[{"aggregations": {"mean": {"a": 80.0}}}])
    await coord.get_ups()
    assert coord.ds["ups"]["battery_charge"] == 80.0


async def test_discover_ups_graphs_returns_none_for_invalid_response() -> None:
    """A None graphs response yields None instead of an empty set."""
    coord = _bare_coordinator()
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value=None)
    assert await coord._discover_ups_graphs() is None


async def test_discover_ups_graphs_filters_known_names() -> None:
    """Only recognized UPS graph names are kept from the discovery response."""
    coord = _bare_coordinator()
    coord.api = MagicMock()
    coord.api.query = AsyncMock(
        return_value=[{"name": "upscharge"}, {"name": "unrelated_graph"}]
    )
    result = await coord._discover_ups_graphs()
    assert result == {"upscharge"}


# ---------------------------
#   get_cloudsync / get_replication / get_rsync / get_snapshottask / get_scrub
# ---------------------------
async def test_get_cloudsync_empty_when_not_monitored() -> None:
    """An unmonitored cloudsync group clears the dict without querying the API."""
    coord = _bare_coordinator()
    coord.ds = {"cloudsync": {"stale": {}}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: []}
    coord.api = MagicMock()
    coord.api.query = AsyncMock()
    await coord.get_cloudsync()
    assert coord.ds["cloudsync"] == {}


async def test_get_cloudsync_parses_when_monitored() -> None:
    """A monitored cloudsync group parses the API response into the dict."""
    coord = _bare_coordinator()
    coord.ds = {"cloudsync": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: [MONITOR_GROUP_CLOUDSYNC]}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value=[{"id": "cs1", "description": "backup"}])
    await coord.get_cloudsync()
    assert "cs1" in coord.ds["cloudsync"]


async def test_get_replication_falls_back_to_job_state() -> None:
    """The nested job.state is flattened onto the entry's own "state" field."""
    coord = _bare_coordinator()
    coord.ds = {"replication": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: [MONITOR_GROUP_REPLICATION]}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(
        return_value=[{"id": 1, "name": "repl1", "job": {"state": "RUNNING"}}]
    )
    await coord.get_replication()
    assert coord.ds["replication"][1]["state"] == "RUNNING"
    assert "job_state" not in coord.ds["replication"][1]


async def test_get_replication_empty_when_not_monitored() -> None:
    """An unmonitored replication group clears the dict without querying the API."""
    coord = _bare_coordinator()
    coord.ds = {"replication": {"stale": {}}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: []}
    coord.api = MagicMock()
    coord.api.query = AsyncMock()
    await coord.get_replication()
    assert coord.ds["replication"] == {}


async def test_get_rsync_empty_when_not_monitored() -> None:
    """An unmonitored rsync group clears the dict without querying the API."""
    coord = _bare_coordinator()
    coord.ds = {"rsynctask": {"stale": {}}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: []}
    coord.api = MagicMock()
    coord.api.query = AsyncMock()
    await coord.get_rsync()
    assert coord.ds["rsynctask"] == {}


async def test_get_rsync_parses_when_monitored() -> None:
    """A monitored rsync group parses the API response into the dict."""
    coord = _bare_coordinator()
    coord.ds = {"rsynctask": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: [MONITOR_GROUP_RSYNC]}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value=[{"id": 1, "path": "/mnt/tank"}])
    await coord.get_rsync()
    assert 1 in coord.ds["rsynctask"]


async def test_get_snapshottask_empty_when_not_monitored() -> None:
    """An unmonitored snapshots group clears the dict without querying the API."""
    coord = _bare_coordinator()
    coord.ds = {"snapshottask": {"stale": {}}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: []}
    coord.api = MagicMock()
    coord.api.query = AsyncMock()
    await coord.get_snapshottask()
    assert coord.ds["snapshottask"] == {}


async def test_get_snapshottask_parses_when_monitored() -> None:
    """A monitored snapshots group parses the entry's schedule into the dict."""
    coord = _bare_coordinator()
    coord.ds = {"snapshottask": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: [MONITOR_GROUP_SNAPSHOTS]}
    coord.api = MagicMock()
    schedule = {"minute": "0", "hour": "*", "dom": "*", "month": "*", "dow": "*"}
    coord.api.query = AsyncMock(
        return_value=[{"id": 1, "dataset": "tank/data", "schedule": schedule}]
    )
    await coord.get_snapshottask()
    assert 1 in coord.ds["snapshottask"]
    assert coord.ds["snapshottask"][1]["schedule"] == schedule


async def test_get_snapshottask_defaults_schedule_when_missing() -> None:
    """A missing schedule field defaults to an empty dict."""
    coord = _bare_coordinator()
    coord.ds = {"snapshottask": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: [MONITOR_GROUP_SNAPSHOTS]}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value=[{"id": 1, "dataset": "tank/data"}])
    await coord.get_snapshottask()
    assert coord.ds["snapshottask"][1]["schedule"] == {}


async def test_get_scrub_parses_response() -> None:
    """A scrub query response is parsed into the scrub dict."""
    coord = _bare_coordinator()
    coord.ds = {"scrub": {}}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value=[{"id": 1, "pool_name": "tank"}])
    await coord.get_scrub()
    assert 1 in coord.ds["scrub"]


# ---------------------------
#   get_app / _clear_finished_app_updates
# ---------------------------
async def test_get_app_catalog_update_available() -> None:
    """An app with a newer catalog version is flagged as having an update."""
    coord = _bare_coordinator()
    coord.ds = {"app": {}}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(
        return_value=[
            {
                "id": "app1",
                "name": "app1",
                "state": "RUNNING",
                "upgrade_available": True,
                "custom_app": False,
                "image_updates_available": False,
            }
        ]
    )
    coord._clear_finished_app_updates = AsyncMock()
    await coord.get_app()
    assert coord.ds["app"]["app1"]["running"] is True
    assert coord.ds["app"]["app1"]["update_available"] is True


async def test_get_app_custom_app_falls_back_to_image_updates() -> None:
    """A custom app's update_available comes from image_updates_available."""
    coord = _bare_coordinator()
    coord.ds = {"app": {}}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(
        return_value=[
            {
                "id": "app1",
                "name": "app1",
                "state": "STOPPED",
                "upgrade_available": False,
                "custom_app": True,
                "image_updates_available": True,
            }
        ]
    )
    coord._clear_finished_app_updates = AsyncMock()
    await coord.get_app()
    assert coord.ds["app"]["app1"]["update_available"] is True


async def test_get_app_no_update_for_noncustom_without_upgrade() -> None:
    """A non-custom app without upgrade_available ignores image_updates_available."""
    coord = _bare_coordinator()
    coord.ds = {"app": {}}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(
        return_value=[
            {
                "id": "app1",
                "name": "app1",
                "state": "STOPPED",
                "upgrade_available": False,
                "custom_app": False,
                "image_updates_available": True,
            }
        ]
    )
    coord._clear_finished_app_updates = AsyncMock()
    await coord.get_app()
    assert coord.ds["app"]["app1"]["update_available"] is False


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
    """An unmonitored cronjobs group clears the dict without querying the API."""
    coord = _bare_coordinator()
    coord.ds = {"cronjob": {"stale": {}}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {CONF_MONITORED_GROUPS: []}
    coord.api = MagicMock()
    coord.api.query = AsyncMock()
    await coord.get_cronjob()
    assert coord.ds["cronjob"] == {}


async def test_get_cronjob_skips_disabled_by_default_behavior() -> None:
    """With the skip-disabled behavior enabled, disabled cronjobs are excluded."""
    coord = _bare_coordinator()
    coord.ds = {"cronjob": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {
        CONF_MONITORED_GROUPS: [MONITOR_GROUP_CRONJOBS],
        CONF_BEHAVIORS: [BEHAVIOR_SKIP_DISABLED_CRONJOBS],
    }
    coord.api = MagicMock()
    coord.api.query = AsyncMock(
        return_value=[
            {"id": 1, "enabled": True, "description": "Job A"},
            {"id": 2, "enabled": False, "description": "Job B"},
        ]
    )
    await coord.get_cronjob()
    assert 1 in coord.ds["cronjob"]
    assert 2 not in coord.ds["cronjob"]
    assert coord.ds["cronjob"][1]["display_name"] == "Job A"


async def test_get_cronjob_keeps_disabled_when_behavior_off() -> None:
    """With the skip-disabled behavior off, disabled cronjobs are still kept."""
    coord = _bare_coordinator()
    coord.ds = {"cronjob": {}}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {
        CONF_MONITORED_GROUPS: [MONITOR_GROUP_CRONJOBS],
        CONF_BEHAVIORS: [],
    }
    coord.api = MagicMock()
    coord.api.query = AsyncMock(
        return_value=[{"id": 2, "enabled": False, "description": "", "command": "ls"}]
    )
    await coord.get_cronjob()
    assert coord.ds["cronjob"][2]["display_name"] == "ls"


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
    coord.api = MagicMock()
    coord.api.query = AsyncMock(
        return_value=[{"id": 3, "enabled": False, "description": "", "command": ""}]
    )
    await coord.get_cronjob()
    assert coord.ds["cronjob"][3]["display_name"] == "Cronjob 3"
