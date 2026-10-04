"""Unit tests for the pure/self-contained helpers and mockable logic in coordinator.py.

Most helpers here are pure functions tested with bare mocks/``SimpleNamespace``.
Instance methods are exercised through a real ``TrueNASCoordinator``, built via
the ``coordinator`` fixture below: a ``hass``/``MockConfigEntry``-driven
construction (mirroring test_init.py's entry-lifecycle tests) with the
``aiotruenas`` client mocked at its boundary (mirroring test_api.py's ``api``
fixture), so production ``__init__``/listener/update behavior is exercised
for real instead of being bypassed via ``__new__``.
"""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.truenas_ce import (
    api as api_module,
    coordinator as coordinator_module,
)
from homeassistant.components.truenas_ce.const import DOMAIN
from homeassistant.components.truenas_ce.coordinator import (
    TrueNASCoordinator,
    _stat_name_similar,
)
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_NAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


@pytest.fixture
def mock_client() -> MagicMock:
    """A mocked aiotruenas client, matching test_api.py's ``api`` fixture."""
    client = MagicMock()
    client.connected = False
    client.connect = AsyncMock()
    client.call = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def coordinator(hass: HomeAssistant, mock_client: MagicMock) -> TrueNASCoordinator:
    """Build a real TrueNASCoordinator via hass/MockConfigEntry.

    The underlying aiotruenas client is mocked at its boundary (like
    test_api.py's ``api`` fixture) so no network I/O happens, while
    __init__/listener/update-relevant instance state is set up for real.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: "TrueNAS",
            CONF_HOST: "truenas.local",
            CONF_API_KEY: "api-key",
            CONF_VERIFY_SSL: True,
        },
        entry_id="e1",
    )
    entry.add_to_hass(hass)
    with patch.object(api_module, "TrueNASClient", return_value=mock_client):
        return TrueNASCoordinator(hass, entry)


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
#   _parse_version
# ---------------------------
def test_parse_version_extracts_major_minor(coordinator: TrueNASCoordinator) -> None:
    """The major/minor version numbers are parsed out of the version string."""
    coord = coordinator
    coord.ds = {"system_info": {"version": "TrueNAS-SCALE-25.04.1"}}
    coord._parse_version()
    assert coord._version_major == 25
    assert coord._version_minor == 4


def test_parse_version_leaves_unset_on_no_match(
    coordinator: TrueNASCoordinator,
) -> None:
    """A version string that does not match the expected pattern leaves fields unset."""
    coord = coordinator
    coord.ds = {"system_info": {"version": "not-a-version-string"}}
    coord._version_major = 0
    coord._version_minor = 0
    coord._parse_version()
    assert coord._version_major == 0
    assert coord._version_minor == 0


# ---------------------------
#   _detect_virtualization
# ---------------------------
def test_detect_virtualization_true_for_known_manufacturer(
    coordinator: TrueNASCoordinator,
) -> None:
    """A known hypervisor manufacturer string is detected as virtual."""
    coord = coordinator
    coord.ds = {"system_info": {"system_manufacturer": "QEMU", "system_product": ""}}
    coord._detect_virtualization()
    assert coord._is_virtual is True


def test_detect_virtualization_true_for_known_product(
    coordinator: TrueNASCoordinator,
) -> None:
    """A known hypervisor product string is detected as virtual."""
    coord = coordinator
    coord.ds = {
        "system_info": {"system_manufacturer": "", "system_product": "VirtualBox"}
    }
    coord._detect_virtualization()
    assert coord._is_virtual is True


def test_detect_virtualization_false_for_physical_hardware(
    coordinator: TrueNASCoordinator,
) -> None:
    """Physical hardware manufacturer/product strings are not detected as virtual."""
    coord = coordinator
    coord.ds = {
        "system_info": {"system_manufacturer": "Dell Inc.", "system_product": "R730"}
    }
    coord._detect_virtualization()
    assert coord._is_virtual is False


# ---------------------------
#   _update_uptime
# ---------------------------
def test_update_uptime_sets_epoch_on_first_run(coordinator: TrueNASCoordinator) -> None:
    """A zero uptimeEpoch is populated from the current uptime on first run."""
    coord = coordinator
    coord.ds = {"system_info": {"uptime_seconds": 3600, "uptimeEpoch": 0}}
    coord._update_uptime()
    assert coord.ds["system_info"]["uptimeEpoch"] > 0


def test_update_uptime_keeps_old_epoch_within_tolerance(
    coordinator: TrueNASCoordinator,
) -> None:
    """An epoch close enough to the freshly computed value is left unchanged."""
    coord = coordinator
    now_epoch = int(dt_util.utcnow().timestamp())
    old_epoch = now_epoch - 3600 + 5  # within the 300s tolerance of a fresh reading
    coord.ds = {"system_info": {"uptime_seconds": 3600, "uptimeEpoch": old_epoch}}
    coord._update_uptime()
    assert coord.ds["system_info"]["uptimeEpoch"] == old_epoch


def test_update_uptime_replaces_stale_epoch_outside_tolerance(
    coordinator: TrueNASCoordinator,
) -> None:
    """An epoch drifted well past tolerance is replaced with a freshly computed one."""
    coord = coordinator
    now_epoch = int(dt_util.utcnow().timestamp())
    old_epoch = now_epoch - 3600 - 600  # 600s drift, well beyond the 300s tolerance
    coord.ds = {"system_info": {"uptime_seconds": 3600, "uptimeEpoch": old_epoch}}
    coord._update_uptime()
    new_epoch = coord.ds["system_info"]["uptimeEpoch"]
    assert new_epoch != old_epoch
    # Replaced by a freshly computed epoch (now - uptime_seconds).
    assert abs(new_epoch - (now_epoch - 3600)) <= 5


def test_update_uptime_skips_when_uptime_not_positive(
    coordinator: TrueNASCoordinator,
) -> None:
    """A non-positive uptime_seconds leaves the existing uptimeEpoch untouched."""
    coord = coordinator
    coord.ds = {"system_info": {"uptime_seconds": 0, "uptimeEpoch": 123}}
    coord._update_uptime()
    assert coord.ds["system_info"]["uptimeEpoch"] == 123


# ---------------------------
#   _systemstats_process / _store_stat_value / _store_stat_defaults
# ---------------------------
def test_systemstats_process_stores_matching_legend_values(
    coordinator: TrueNASCoordinator,
) -> None:
    """Each legend var's mean value is stored, missing means falling back to 0.0."""
    coord = coordinator
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


def test_systemstats_process_falls_back_to_defaults_without_aggregations(
    coordinator: TrueNASCoordinator,
) -> None:
    """A graph with no aggregations stores default (0.0) values for each var."""
    coord = coordinator
    coord.ds = {"system_info": {}}
    coord._systemstats_process("cpu", {}, "cpu")
    assert coord.ds["system_info"]["cpu_cpu"] == pytest.approx(0.0)


def test_systemstats_process_defaults_use_dedicated_keys(
    coordinator: TrueNASCoordinator,
) -> None:
    """Defaults for a malformed graph land under the same key as a real value.

    A regression test for a bug where defaults bypassed the type-specific
    key mapping in _store_stat_value and were written under the bare var
    name instead, leaving the actually-exposed sensor keys stale.
    """
    coord = coordinator
    coord.ds = {"system_info": {}}
    coord._systemstats_process("size", {}, "arcsize")
    assert coord.ds["system_info"]["cache_size-arc_value"] == 0.0
    coord._systemstats_process("available", {}, "memory")
    assert coord.ds["system_info"]["memory-free_value"] == 0


def test_systemstats_process_skips_legend_var_not_in_arr(
    coordinator: TrueNASCoordinator,
) -> None:
    """A legend var absent from the vars tuple is not stored."""
    coord = coordinator
    coord.ds = {"system_info": {}}
    graph = {
        "legend": ["shortterm", "other"],
        "aggregations": {"mean": {"shortterm": 1.0, "other": 99.0}},
    }
    coord._systemstats_process(("shortterm",), graph, "load")
    assert coord.ds["system_info"]["load_shortterm"] == pytest.approx(1.0)
    assert "load_other" not in coord.ds["system_info"]


def test_store_stat_value_arcsize_uses_dedicated_key(
    coordinator: TrueNASCoordinator,
) -> None:
    """The arcsize/size stat is rounded and stored under its dedicated key."""
    coord = coordinator
    coord.ds = {"system_info": {}}
    coord._store_stat_value("arcsize", "size", 12.345)
    assert coord.ds["system_info"]["cache_size-arc_value"] == pytest.approx(12.35)


def test_store_stat_value_cpu_uses_prefixed_key(
    coordinator: TrueNASCoordinator,
) -> None:
    """The cpu stat is stored under a "<type>_<var>" prefixed key."""
    coord = coordinator
    coord.ds = {"system_info": {}}
    coord._store_stat_value("cpu", "cpu", 12.345)
    assert coord.ds["system_info"]["cpu_cpu"] == pytest.approx(12.35)


def test_store_stat_value_memory_only_stores_available(
    coordinator: TrueNASCoordinator,
) -> None:
    """Only the memory "available" var is stored; other memory vars are ignored."""
    coord = coordinator
    coord.ds = {"system_info": {}}
    coord._store_stat_value("memory", "available", 100.0)
    assert coord.ds["system_info"]["memory-free_value"] == 100
    coord._store_stat_value("memory", "used", 50.0)
    assert "memory-used" not in coord.ds["system_info"]


def test_store_stat_value_unknown_type_stores_raw_key(
    coordinator: TrueNASCoordinator,
) -> None:
    """An unrecognized stat type falls back to storing under the raw var name."""
    coord = coordinator
    coord.ds = {"system_info": {}}
    coord._store_stat_value("diskstats", "reads", 12.345)
    assert coord.ds["system_info"]["reads"] == pytest.approx(12.35)


# ---------------------------
#   connected
# ---------------------------
# Note: TrueNASCoordinator.__init__ itself is not unit-tested here -- HA's
# DataUpdateCoordinator.__init__ calls frame.report_usage(), which requires
# hass's frame helper to have been set up by a running Home Assistant core
# (unavailable via pytest-homeassistant-custom-component on this Windows dev
# machine). It is exercised by CI's hass-fixture-based integration tests.
def test_connected_delegates_to_api(coordinator: TrueNASCoordinator) -> None:
    """coord.connected() delegates directly to the API's connected() call."""
    coord = coordinator
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    assert coord.connected() is True
    coord.api.connected.assert_called_once()


# ---------------------------
#   _async_ensure_connected
# ---------------------------
async def test_async_ensure_connected_noop_when_already_connected(
    coordinator: TrueNASCoordinator,
) -> None:
    """An already-connected API is not asked to connect again."""
    coord = coordinator
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.connect = AsyncMock()
    await coord._async_ensure_connected()
    coord.api.connect.assert_not_awaited()


async def test_async_ensure_connected_raises_update_failed_on_exception(
    coordinator: TrueNASCoordinator,
) -> None:
    """A connect() exception is translated into UpdateFailed."""
    coord = coordinator
    coord.host = "truenas.local"
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=False)
    coord.api.connect = AsyncMock(side_effect=Exception("boom"))
    with pytest.raises(coordinator_module.UpdateFailed):
        await coord._async_ensure_connected()


async def test_async_ensure_connected_raises_update_failed_on_invalid_key(
    coordinator: TrueNASCoordinator,
) -> None:
    """An ERR_INVALID_KEY connect failure is translated into UpdateFailed.

    Bronze scope has no reauth flow to hand off to, so this degrades to the
    same UpdateFailed/entity-unavailable path as any other connection failure
    instead of ConfigEntryAuthFailed (see coordinator._async_ensure_connected).
    """
    coord = coordinator
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


async def test_async_ensure_connected_raises_update_failed_on_other_error(
    coordinator: TrueNASCoordinator,
) -> None:
    """A non-auth connect failure is translated into UpdateFailed."""
    coord = coordinator
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=False)
    coord.api.connect = AsyncMock(return_value=False)
    coord.api.error = "ERR_LOST_QUERY"
    coord.host = "truenas.local"
    with pytest.raises(coordinator_module.UpdateFailed):
        await coord._async_ensure_connected()


async def test_async_ensure_connected_succeeds(coordinator: TrueNASCoordinator) -> None:
    """A successful connect() call completes without raising."""
    coord = coordinator
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=False)
    coord.api.connect = AsyncMock(return_value=True)
    await coord._async_ensure_connected()  # must not raise


async def test_async_ensure_connected_relogs_error_when_failure_reason_changes(
    coordinator: TrueNASCoordinator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failure cause change mid-outage must re-log ERROR once.

    It must not stay silently pinned to DEBUG for whatever error code was
    first seen -- the dedup marker persists the ERR_* code itself (see
    _connection_failing_error), not just a bare failing/not-failing bool, so
    this must be re-detected even without a recovery in between.
    """
    coord = coordinator
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=False)
    coord.api.connect = AsyncMock(return_value=False)
    coord.api.error = "ERR_LOST_QUERY"
    coord.host = "truenas.local"

    with caplog.at_level("DEBUG", logger=coordinator_module.__name__):
        with pytest.raises(coordinator_module.UpdateFailed):
            await coord._async_ensure_connected()
        assert coord._connection_failing_error == "ERR_LOST_QUERY"

        # Same cause again: still deduped to DEBUG, no new ERROR.
        caplog.clear()
        with pytest.raises(coordinator_module.UpdateFailed):
            await coord._async_ensure_connected()
        assert not any(r.levelname == "ERROR" for r in caplog.records)

        # Cause changes without ever recovering in between.
        caplog.clear()
        coord.api.error = "ERR_LOST_LOGIN"
        with pytest.raises(coordinator_module.UpdateFailed):
            await coord._async_ensure_connected()
        assert any(
            r.levelname == "ERROR" and "failure changed" in r.message
            for r in caplog.records
        )
        assert coord._connection_failing is True
        assert coord._connection_failing_error == "ERR_LOST_LOGIN"
        # Must actually go through the setter (re-persisting into hass.data),
        # not just reassign the in-memory attribute -- otherwise a later
        # setup-retry recreation would seed the stale pre-change code again.
        assert (
            coordinator_module._seed_connection_failing(coord.hass, coord.config_entry)
            == "ERR_LOST_LOGIN"
        )

        # The new cause is now itself deduped to DEBUG on repeat.
        caplog.clear()
        with pytest.raises(coordinator_module.UpdateFailed):
            await coord._async_ensure_connected()
        assert not any(r.levelname == "ERROR" for r in caplog.records)


async def test_connection_failing_survives_coordinator_recreation(
    hass: HomeAssistant,
    mock_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Dedup (and the seeded ERR_* code) must survive a setup-retry recreation.

    A setup retry recreates the coordinator (see async_setup_entry), which
    would otherwise reset _connection_failing to False and re-log a fresh
    ERROR every ~10 minutes (the setup-retry backoff cap) while TrueNAS stays
    down. The hass.data mirror written by _set_connection_failing must let a
    *second*, freshly-constructed coordinator instance for the same config
    entry pick the dedup back up (via TrueNASCoordinator.__init__'s own
    seeding, exercised here for real) and actually behave like a repeat
    failure (DEBUG, not ERROR).
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: "TrueNAS",
            CONF_HOST: "truenas.local",
            CONF_API_KEY: "api-key",
            CONF_VERIFY_SSL: True,
        },
        entry_id="e1",
    )
    entry.add_to_hass(hass)

    with patch.object(api_module, "TrueNASClient", return_value=mock_client):
        coord = TrueNASCoordinator(hass, entry)
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=False)
    coord.api.connect = AsyncMock(return_value=False)
    coord.api.error = "ERR_LOST_QUERY"
    coord.host = "truenas.local"

    with pytest.raises(coordinator_module.UpdateFailed):
        await coord._async_ensure_connected()
    assert coord._connection_failing is True

    with patch.object(api_module, "TrueNASClient", return_value=mock_client):
        coord2 = TrueNASCoordinator(hass, entry)
    # Seeded straight from __init__, before any reconnect attempt on coord2.
    assert coord2._connection_failing is True
    assert coord2._connection_failing_error == "ERR_LOST_QUERY"
    coord2.api = MagicMock()
    coord2.api.connected = MagicMock(return_value=False)
    coord2.api.connect = AsyncMock(return_value=False)
    coord2.api.error = "ERR_LOST_QUERY"
    coord2.host = "truenas.local"

    caplog.clear()
    with caplog.at_level("DEBUG", logger=coordinator_module.__name__):
        with pytest.raises(coordinator_module.UpdateFailed):
            await coord2._async_ensure_connected()
        assert not any(r.levelname == "ERROR" for r in caplog.records)
        assert any(
            r.levelname == "DEBUG" and "still failing" in r.message
            for r in caplog.records
        )
        coord2.api.connect.assert_awaited_with(quiet=True)

    # Recovery on either instance clears the persisted marker too.
    coord2.api.connected = MagicMock(return_value=True)
    await coord2._async_ensure_connected()  # must not raise
    assert coord2._connection_failing is False
    assert coordinator_module._seed_connection_failing(hass, entry) is None


def _config_entry_stub(
    *,
    entry_id: str = "entry1",
    host: str = "truenas.local",
    api_key: str = "key1",
    verify_ssl: bool = True,
) -> SimpleNamespace:
    """Bare stand-in for a ConfigEntry, for the pure hass.data helpers below."""
    return SimpleNamespace(
        entry_id=entry_id,
        data={CONF_HOST: host, CONF_API_KEY: api_key, CONF_VERIFY_SSL: verify_ssl},
    )


def test_seed_connection_failing_defaults_to_none() -> None:
    """No persisted marker means a freshly seeded coordinator starts clean."""
    hass = SimpleNamespace(data={})
    entry = _config_entry_stub()
    assert coordinator_module._seed_connection_failing(hass, entry) is None


def test_seed_connection_failing_reads_persisted_marker() -> None:
    """A persisted marker is returned only for the matching entry_id."""
    entry = _config_entry_stub()
    other_entry = _config_entry_stub(entry_id="other-entry")
    hass = SimpleNamespace(
        data={
            DOMAIN: {
                coordinator_module._DATA_CONNECTION_FAILING: {
                    "entry1": (
                        coordinator_module._connection_fingerprint(entry),
                        "ERR_LOST_QUERY",
                    )
                }
            }
        }
    )
    assert coordinator_module._seed_connection_failing(hass, entry) == "ERR_LOST_QUERY"
    assert coordinator_module._seed_connection_failing(hass, other_entry) is None


def test_seed_connection_failing_ignores_marker_for_different_target() -> None:
    """A marker left by a since-reconfigured host/API key must not carry over.

    Reproduces the #145 follow-up's critical gap: reconfiguring away from a
    config entry stuck in Home Assistant's SETUP_RETRY state never calls
    async_unload_entry (see clear_persisted_connection_failing's docstring),
    so the marker can only be neutralized here, by fingerprint mismatch, not
    by being explicitly cleared.
    """
    entry = _config_entry_stub()
    hass = SimpleNamespace(
        data={
            DOMAIN: {
                coordinator_module._DATA_CONNECTION_FAILING: {
                    "entry1": (
                        coordinator_module._connection_fingerprint(entry),
                        "ERR_LOST_QUERY",
                    )
                }
            }
        }
    )
    reconfigured_entry = _config_entry_stub(host="truenas-new.local")
    assert coordinator_module._seed_connection_failing(hass, reconfigured_entry) is None


def test_seed_connection_failing_ignores_marker_for_changed_verify_ssl() -> None:
    """A reconfigure that only flips CONF_VERIFY_SSL must also invalidate the marker.

    CONF_VERIFY_SSL is set via the same reconfigure flow as host/API key and
    changes how the connection is actually established, so it belongs in the
    fingerprint alongside them -- otherwise the first failure after such a
    reconfigure stays wrongly deduped to DEBUG instead of producing a fresh
    ERROR diagnostic.
    """
    entry = _config_entry_stub(verify_ssl=True)
    hass = SimpleNamespace(
        data={
            DOMAIN: {
                coordinator_module._DATA_CONNECTION_FAILING: {
                    "entry1": (
                        coordinator_module._connection_fingerprint(entry),
                        "ERR_LOST_QUERY",
                    )
                }
            }
        }
    )
    reconfigured_entry = _config_entry_stub(verify_ssl=False)
    assert coordinator_module._seed_connection_failing(hass, reconfigured_entry) is None


def test_clear_persisted_connection_failing_removes_entry() -> None:
    """Clearing removes only the target entry's marker, leaving others intact."""
    hass = SimpleNamespace(
        data={
            DOMAIN: {
                coordinator_module._DATA_CONNECTION_FAILING: {
                    "entry1": ("fingerprint1", "ERR_LOST_QUERY"),
                    "entry2": ("fingerprint2", "ERR_LOST_LOGIN"),
                }
            }
        }
    )
    coordinator_module.clear_persisted_connection_failing(hass, "entry1")
    by_entry = hass.data[DOMAIN][coordinator_module._DATA_CONNECTION_FAILING]
    assert by_entry == {"entry2": ("fingerprint2", "ERR_LOST_LOGIN")}


def test_clear_persisted_connection_failing_noop_when_absent() -> None:
    """Clearing a marker that was never set is a no-op, not an error."""
    hass = SimpleNamespace(data={})
    coordinator_module.clear_persisted_connection_failing(hass, "entry1")  # no raise


# ---------------------------
#   _async_update_data
# ---------------------------
def _stub_all_jobs(coord: TrueNASCoordinator) -> None:
    """Patch every job invoked by ``_async_update_data`` with a no-op AsyncMock."""
    for name in (
        "get_systeminfo",
        "get_systemstats",
    ):
        stub = AsyncMock()
        # _run_job derives the job key from __name__; keep it realistic so
        # _note_job_outcome/is_data_path_failing see the true job name.
        stub.__name__ = name
        setattr(coord, name, stub)


async def test_async_update_data_runs_jobs_when_connected(
    coordinator: TrueNASCoordinator,
) -> None:
    """All get_* jobs run and the coordinator's ds dict is returned when connected."""
    coord = coordinator
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord._async_ensure_connected = AsyncMock()
    _stub_all_jobs(coord)
    coord.ds = {"foo": "bar", "system_info": {"hostname": "truenas"}}

    result = await coord._async_update_data()

    coord.get_systeminfo.assert_awaited_once()
    coord.get_systemstats.assert_awaited_once()
    assert result is coord.ds


async def test_async_update_data_raises_when_hostname_missing_or_unknown(
    coordinator: TrueNASCoordinator,
) -> None:
    """A dict-shaped system_info reply without a real hostname fails the poll.

    ``get_systeminfo`` is stubbed as a no-op here, so ``ds["system_info"]``
    keeps whatever was set beforehand -- this simulates the field being
    missing entirely or still carrying the "unknown" default.
    """
    coord = coordinator
    coord.host = "truenas.local"
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord._async_ensure_connected = AsyncMock()
    _stub_all_jobs(coord)

    for system_info in ({}, {"hostname": "unknown"}):
        coord.ds = {"system_info": system_info}

        with pytest.raises(coordinator_module.UpdateFailed):
            await coord._async_update_data()

        coord.get_systeminfo.assert_awaited_once()
        coord.get_systemstats.assert_not_awaited()
        coord.get_systeminfo.reset_mock()


async def test_async_update_data_raises_when_hostname_is_none_or_empty(
    coordinator: TrueNASCoordinator,
) -> None:
    """A None/empty hostname is rejected same as a missing/unknown one.

    ensure_vals only backfills a default when the key is absent, not when
    it's explicitly null/empty -- so that must be checked separately.
    """
    coord = coordinator
    coord.host = "truenas.local"
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord._async_ensure_connected = AsyncMock()
    _stub_all_jobs(coord)

    for bad_hostname in (None, ""):
        coord.ds = {"system_info": {"hostname": bad_hostname}}

        with pytest.raises(coordinator_module.UpdateFailed):
            await coord._async_update_data()

        coord.get_systeminfo.assert_awaited_once()
        coord.get_systemstats.assert_not_awaited()
        coord.get_systeminfo.reset_mock()


async def test_async_update_data_skips_jobs_when_disconnected(
    coordinator: TrueNASCoordinator,
) -> None:
    """A still-disconnected API raises UpdateFailed and skips running any jobs."""
    coord = coordinator
    coord.host = "truenas.local"
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=False)
    coord._async_ensure_connected = AsyncMock()
    _stub_all_jobs(coord)

    with pytest.raises(coordinator_module.UpdateFailed):
        await coord._async_update_data()

    coord.get_systeminfo.assert_not_awaited()


async def test_async_update_data_swallows_job_exceptions(
    coordinator: TrueNASCoordinator,
) -> None:
    """A single job raising an exception does not abort the overall update."""
    coord = coordinator
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord._async_ensure_connected = AsyncMock()
    _stub_all_jobs(coord)
    coord.get_systemstats = AsyncMock(side_effect=Exception("boom"))
    coord.ds = {"system_info": {"hostname": "truenas"}}

    result = await coord._async_update_data()  # must not raise

    assert result is coord.ds


async def test_async_update_data_raises_when_system_info_missing(
    coordinator: TrueNASCoordinator,
) -> None:
    """A first refresh missing system.info must not be reported as successful."""
    coord = coordinator
    coord.host = "truenas.local"
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord._async_ensure_connected = AsyncMock()
    _stub_all_jobs(coord)
    coord.ds = {"system_info": {}}

    with pytest.raises(coordinator_module.UpdateFailed):
        await coord._async_update_data()

    coord.get_systeminfo.assert_awaited_once()
    coord.get_systemstats.assert_not_awaited()


async def test_run_job_does_not_log_recovery_when_disconnected_mid_job(
    caplog: pytest.LogCaptureFixture, coordinator: TrueNASCoordinator
) -> None:
    """A job returning cleanly right as the connection drops isn't "recovered".

    Logging a recovery here would be misleading: this same poll goes on to
    raise "disconnected" a few lines later, so nothing actually recovered --
    the job-failing flag must stay set until a poll where the job actually
    completes while still connected.
    """
    coord = coordinator
    coord.host = "truenas.local"
    coord._job_failing["get_systeminfo"] = True
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord._async_ensure_connected = AsyncMock()
    _stub_all_jobs(coord)
    coord.ds = {"system_info": {"hostname": "truenas"}}

    async def fake_get_systeminfo() -> None:
        # Simulate the connection dropping during the job's own work.
        coord.api.connected = MagicMock(return_value=False)

    fake_get_systeminfo.__name__ = "get_systeminfo"
    coord.get_systeminfo = fake_get_systeminfo

    with caplog.at_level("INFO"), pytest.raises(coordinator_module.UpdateFailed):
        await coord._async_update_data()

    assert "get_systeminfo recovered" not in caplog.text
    assert coord.is_data_path_failing("system_info") is True


# ---------------------------
#   _note_job_outcome / is_data_path_failing
# ---------------------------
def test_note_job_outcome_reports_only_the_first_failure(
    coordinator: TrueNASCoordinator,
) -> None:
    """The transition into failing returns True once; repeats return False."""
    coord = coordinator

    assert coord._note_job_outcome("get_systeminfo", failed=True) is True
    assert coord._note_job_outcome("get_systeminfo", failed=True) is False
    assert coord.is_data_path_failing("system_info") is True


def test_note_job_outcome_logs_recovery_once_and_clears_flag(
    caplog: pytest.LogCaptureFixture, coordinator: TrueNASCoordinator
) -> None:
    """A success after a failure logs an info recovery and resets the flag."""
    coord = coordinator
    coord._note_job_outcome("get_systeminfo", failed=True)

    with caplog.at_level("INFO"):
        coord._note_job_outcome("get_systeminfo", failed=False)
        coord._note_job_outcome("get_systeminfo", failed=False)

    assert coord.is_data_path_failing("system_info") is False
    assert caplog.text.count("TrueNAS job get_systeminfo recovered") == 1


async def test_is_data_path_failing_stays_false_for_a_job_that_never_failed(
    caplog: pytest.LogCaptureFixture, coordinator: TrueNASCoordinator
) -> None:
    """A clean poll leaves every data_path available and logs no failure."""
    coord = coordinator
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord._async_ensure_connected = AsyncMock()
    _stub_all_jobs(coord)
    coord.ds = {"system_info": {"hostname": "truenas"}}

    with caplog.at_level("DEBUG"):
        await coord._async_update_data()

    assert "failed" not in caplog.text
    assert coord.is_data_path_failing("system_info") is False


async def test_is_data_path_failing_covers_every_path_of_a_multi_path_job(
    coordinator: TrueNASCoordinator,
) -> None:
    """A failing get_systeminfo marks both ds keys it owns, then clears them."""
    coord = coordinator
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord._async_ensure_connected = AsyncMock()
    _stub_all_jobs(coord)
    coord.ds = {"system_info": {"hostname": "truenas"}}
    failing_systeminfo = AsyncMock(side_effect=Exception("boom"))
    failing_systeminfo.__name__ = "get_systeminfo"
    coord.get_systeminfo = failing_systeminfo

    await coord._async_update_data()

    assert coord.is_data_path_failing("system_info") is True
    assert coord.is_data_path_failing("interface") is True

    recovered_systeminfo = AsyncMock()
    recovered_systeminfo.__name__ = "get_systeminfo"
    coord.get_systeminfo = recovered_systeminfo

    await coord._async_update_data()

    assert coord.is_data_path_failing("system_info") is False
    assert coord.is_data_path_failing("interface") is False


# ---------------------------
#   get_systeminfo / _handle_update_job / _query_interfaces
# ---------------------------
async def test_get_systeminfo_parses_valid_response_and_runs_pipeline(
    coordinator: TrueNASCoordinator,
) -> None:
    """A valid system-info response is parsed and the update-job pipeline runs."""
    coord = coordinator
    coord.ds = {"system_info": {}, "interface": {}}
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)

    async def fake_query(method: str, *_args: object, **_kwargs: object) -> object:
        if method == "system.info":
            return {
                "version": "TrueNAS-SCALE-25.04.1",
                "hostname": "nas1",
                "uptime_seconds": 100,
                "physmem": 1000,
            }
        return []

    coord.api.query = AsyncMock(side_effect=fake_query)
    coord._handle_update_job = AsyncMock()

    await coord.get_systeminfo()

    assert coord.ds["system_info"]["hostname"] == "nas1"
    assert coord.ds["system_info"]["update_version"] == "TrueNAS-SCALE-25.04.1"
    assert coord._version_major == 25
    coord._handle_update_job.assert_awaited_once()


async def test_get_systeminfo_raises_on_invalid_response(
    coordinator: TrueNASCoordinator,
) -> None:
    """A None system-info response fails the job so its entities go unavailable."""
    coord = coordinator
    coord.host = "truenas.local"
    coord.ds = {"system_info": {}, "interface": {}}
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.query = AsyncMock(return_value=None)
    coord._handle_update_job = AsyncMock()

    with pytest.raises(coordinator_module.UpdateFailed) as exc_info:
        await coord.get_systeminfo()

    assert exc_info.value.translation_key == "system_info_unavailable"
    assert exc_info.value.translation_placeholders == {"host": "truenas.local"}
    coord._handle_update_job.assert_not_awaited()


async def test_get_systeminfo_returns_early_when_disconnected_after_parse(
    coordinator: TrueNASCoordinator,
) -> None:
    """Disconnection after parsing returns early before the update-job pipeline."""
    coord = coordinator
    coord.ds = {"system_info": {}, "interface": {}}
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=False)
    coord.api.query = AsyncMock(return_value={"version": "25.04.1"})
    coord._handle_update_job = AsyncMock()

    await coord.get_systeminfo()

    coord._handle_update_job.assert_not_awaited()


async def test_get_systeminfo_returns_early_disconnected_after_update_job(
    coordinator: TrueNASCoordinator,
) -> None:
    """Disconnection right after the update job skips further version parsing."""
    coord = coordinator
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


async def test_handle_update_job_noop_without_jobid(
    coordinator: TrueNASCoordinator,
) -> None:
    """A zero update_jobid means no job status query is made."""
    coord = coordinator
    coord.ds = {"system_info": {"update_jobid": 0}}
    coord.api = MagicMock()
    coord.api.query = AsyncMock()
    await coord._handle_update_job()
    coord.api.query.assert_not_awaited()


async def test_handle_update_job_keeps_progress_while_running(
    coordinator: TrueNASCoordinator,
) -> None:
    """A RUNNING update job's progress percentage and state are stored."""
    coord = coordinator
    coord.ds = {"system_info": {"update_jobid": 5, "update_available": True}}
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.query = AsyncMock(
        return_value={"progress": {"percent": 42}, "state": "RUNNING"}
    )
    await coord._handle_update_job()
    assert coord.ds["system_info"]["update_progress"] == 42
    assert coord.ds["system_info"]["update_state"] == "RUNNING"


async def test_handle_update_job_resets_when_finished(
    coordinator: TrueNASCoordinator,
) -> None:
    """A finished (SUCCESS) update job resets jobid/progress/state to idle defaults."""
    coord = coordinator
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


async def test_handle_update_job_returns_early_when_disconnected(
    coordinator: TrueNASCoordinator,
) -> None:
    """A disconnected API leaves the existing update_jobid untouched."""
    coord = coordinator
    coord.ds = {"system_info": {"update_jobid": 5}}
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=False)
    coord.api.query = AsyncMock(return_value=None)
    await coord._handle_update_job()
    assert coord.ds["system_info"]["update_jobid"] == 5


async def test_query_interfaces_derives_link_up(
    coordinator: TrueNASCoordinator,
) -> None:
    """Each interface's link_up flag is derived from its reported link state."""
    coord = coordinator
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


async def test_query_interfaces_raises_on_invalid_response(
    coordinator: TrueNASCoordinator,
) -> None:
    """A None interface.query response fails the job instead of being swallowed.

    Without this check, a failed ``interface.query`` call silently kept the
    previous snapshot forever, so interface entities never went unavailable.
    """
    coord = coordinator
    coord.host = "truenas.local"
    coord.ds = {"interface": {}}
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)
    coord.api.query = AsyncMock(return_value=None)

    with pytest.raises(coordinator_module.UpdateFailed) as exc_info:
        await coord._query_interfaces()

    assert exc_info.value.translation_key == "interface_unavailable"
    assert exc_info.value.translation_placeholders == {"host": "truenas.local"}


async def test_query_interfaces_skips_raise_when_disconnected_mid_query(
    coordinator: TrueNASCoordinator,
) -> None:
    """A mid-query disconnect is left to _async_update_data's own error.

    Raising "interface_unavailable" here too would misattribute a plain
    disconnect as an interface-specific failure.
    """
    coord = coordinator
    coord.ds = {"interface": {}}
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=False)
    coord.api.query = AsyncMock(return_value=None)

    await coord._query_interfaces()


async def test_query_interfaces_accepts_empty_list(
    coordinator: TrueNASCoordinator,
) -> None:
    """An empty interface list is valid data (zero interfaces), not a failure.

    parse_api's own pruning (_empty_source_result with source_was_none=False)
    drops the previous snapshot entirely rather than keeping it as stale.
    """
    coord = coordinator
    coord.ds = {"interface": {"eth0": {"id": "eth0", "name": "eth0"}}}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value=[])

    await coord._query_interfaces()

    assert coord.ds["interface"] == {}


async def test_get_systeminfo_tracks_interface_failure_separately(
    coordinator: TrueNASCoordinator,
) -> None:
    """A lone interface.query failure marks only "interface" unavailable.

    system_info was already parsed successfully earlier in the same poll, so
    get_systeminfo() must not re-raise the interface.query failure -- doing
    so would also mark the ten unrelated system_info entities unavailable.
    """
    coord = coordinator
    coord.host = "truenas.local"
    coord.ds = {"system_info": {}, "interface": {}}
    coord.api = MagicMock()
    coord.api.connected = MagicMock(return_value=True)

    async def fake_query(method: str, *_args: object, **_kwargs: object) -> object:
        if method == "system.info":
            return {"version": "TrueNAS-SCALE-25.04.1", "hostname": "nas1"}
        return None

    coord.api.query = AsyncMock(side_effect=fake_query)
    coord._handle_update_job = AsyncMock()

    await coord.get_systeminfo()

    assert coord.is_data_path_failing("interface") is True
    assert coord.is_data_path_failing("system_info") is False


# ---------------------------
#   get_systemstats family
# ---------------------------
def test_select_stat_graph_names_includes_interface_when_present(
    coordinator: TrueNASCoordinator,
) -> None:
    """The interface graph is included whenever interfaces exist."""
    coord = coordinator
    coord.ds = {"interface": {"eth0": {}}}
    coord._is_virtual = False
    coord._systemstats_errored = {}
    names = coord._select_stat_graph_names()
    assert "interface" in names
    assert "cputemp" in names


def test_select_stat_graph_names_removes_cputemp_for_virtual(
    coordinator: TrueNASCoordinator,
) -> None:
    """A virtual machine drops cputemp, and no interfaces drops the interface graph."""
    coord = coordinator
    coord.ds = {"interface": {}}
    coord._is_virtual = True
    coord._systemstats_errored = {}
    names = coord._select_stat_graph_names()
    assert "cputemp" not in names
    assert "interface" not in names


def test_select_stat_graph_names_filters_cooldown_graphs(
    coordinator: TrueNASCoordinator,
) -> None:
    """A graph that recently errored is excluded while still in its cooldown."""
    coord = coordinator
    coord.ds = {"interface": {}}
    coord._is_virtual = False
    coord._systemstats_errored = {"cpu": dt_util.utcnow()}
    coord._systemstats_error_cooldown = timedelta(minutes=10)
    names = coord._select_stat_graph_names()
    assert "cpu" not in names


async def test_fetch_stat_graphs_collects_and_records_failures(
    coordinator: TrueNASCoordinator,
) -> None:
    """Successful graph queries are collected and failed ones are recorded."""
    coord = coordinator
    coord.host = "truenas.local"
    coord._systemstats_errored = {}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(side_effect=[[{"name": "load"}], None])
    result = await coord._fetch_stat_graphs(["load", "cpu"], {"start": 0, "end": 1})
    assert result == [{"name": "load"}]
    assert "cpu" in coord._systemstats_errored


def test_record_failed_graphs_logs_only_new_failures(
    caplog: pytest.LogCaptureFixture, coordinator: TrueNASCoordinator
) -> None:
    """Only a graph not already in the errored dict is warned about (new failure)."""
    coord = coordinator
    coord.host = "truenas.local"
    coord._systemstats_errored = {"cpu": dt_util.utcnow()}
    with caplog.at_level("WARNING"):
        coord._record_failed_graphs(["cpu", "memory"])
    assert "memory" in caplog.text
    assert coord._systemstats_errored.keys() == {"cpu", "memory"}


def test_record_failed_graphs_noop_for_empty_list(
    coordinator: TrueNASCoordinator,
) -> None:
    """An empty failed-graphs list leaves the errored dict untouched."""
    coord = coordinator
    coord._systemstats_errored = {}
    coord._record_failed_graphs([])
    assert coord._systemstats_errored == {}


def test_process_system_stat_dispatches_by_name(
    coordinator: TrueNASCoordinator,
) -> None:
    """A "load" stat item with no aggregations falls back to zeroed defaults."""
    coord = coordinator
    coord.ds = {"system_info": {}, "interface": {}}
    # Missing "aggregations"/"legend" fails the isinstance guard in
    # _systemstats_process, so it falls back to _store_stat_defaults, which
    # routes through _store_stat_value the same as a successful value would.
    coord._process_system_stat({"name": "load"})
    assert coord.ds["system_info"]["load_shortterm"] == 0.0


def test_process_system_stat_ignores_missing_name(
    coordinator: TrueNASCoordinator,
) -> None:
    """A stat item without a "name" key is ignored instead of raising."""
    coord = coordinator
    coord.ds = {"system_info": {}}
    coord._process_system_stat({})  # must not raise


def test_process_system_stat_dispatches_cputemp(
    coordinator: TrueNASCoordinator,
) -> None:
    """A "cputemp" stat item is dispatched to _process_cputemp."""
    coord = coordinator
    coord.ds = {"system_info": {}}
    item = {"name": "cputemp", "aggregations": {"mean": {"core0": 40.0}}}
    with patch.object(coord, "_process_cputemp") as mock:
        coord._process_system_stat(item)
    mock.assert_called_once_with(item)


def test_process_system_stat_dispatches_cpu_and_rounds_usage(
    coordinator: TrueNASCoordinator,
) -> None:
    """A "cpu" stat item derives cpu_usage from the (defaulted) cpu_cpu value."""
    coord = coordinator
    coord.ds = {"system_info": {}}
    coord._process_system_stat({"name": "cpu"})
    # No aggregations/legend -> _store_stat_defaults zeroes cpu_cpu, which then
    # feeds cpu_usage.
    assert coord.ds["system_info"]["cpu_usage"] == pytest.approx(0.0)


def test_process_system_stat_dispatches_interface_for_known_identifier(
    coordinator: TrueNASCoordinator,
) -> None:
    """An interface stat item for a tracked identifier updates its rx/tx values."""
    coord = coordinator
    coord.ds = {"system_info": {}, "interface": {"eth0": {}}}
    coord._process_system_stat(
        {"name": "interface", "identifier": "eth0", "legend": "not-a-list"}
    )
    assert coord.ds["interface"]["eth0"]["rx"] == 0.0
    assert coord.ds["interface"]["eth0"]["tx"] == 0.0


def test_process_system_stat_ignores_interface_for_unknown_identifier(
    coordinator: TrueNASCoordinator,
) -> None:
    """An interface stat item for an untracked identifier is ignored."""
    coord = coordinator
    coord.ds = {"system_info": {}, "interface": {}}
    coord._process_system_stat({"name": "interface", "identifier": "eth99"})
    assert coord.ds["interface"] == {}


def test_process_system_stat_dispatches_memory(coordinator: TrueNASCoordinator) -> None:
    """A "memory" stat item is dispatched to the memory-specific processor."""
    coord = coordinator
    coord.ds = {"system_info": {"physmem": 1000}}
    coord._process_system_stat(
        {
            "name": "memory",
            "legend": ["available"],
            "aggregations": {"mean": {"available": 250.0}},
        }
    )
    assert coord.ds["system_info"]["memory-free_value"] == 250


def test_process_system_stat_dispatches_arcsize(
    coordinator: TrueNASCoordinator,
) -> None:
    """An "arcsize" stat item is stored under the dedicated ARC cache key."""
    coord = coordinator
    coord.ds = {"system_info": {}}
    coord._process_system_stat(
        {
            "name": "arcsize",
            "legend": ["size"],
            "aggregations": {"mean": {"size": 12.345}},
        }
    )
    assert coord.ds["system_info"]["cache_size-arc_value"] == pytest.approx(12.35)


def test_process_system_stat_dispatches_unknown_name(
    coordinator: TrueNASCoordinator,
) -> None:
    """An unrecognized stat name is recorded in the unknown-stat-names set."""
    coord = coordinator
    coord.ds = {"system_info": {}}
    coord.host = "truenas.local"
    coord._unknown_system_stat_names = set()
    coord._process_system_stat({"name": "weird_stat"})
    assert "weird_stat" in coord._unknown_system_stat_names


def test_process_cputemp_stores_max_mean(coordinator: TrueNASCoordinator) -> None:
    """cpu_temperature is set to the highest mean core temperature."""
    coord = coordinator
    coord.ds = {"system_info": {}}
    coord._process_cputemp({"aggregations": {"mean": {"core0": 40.0, "core1": 45.0}}})
    assert coord.ds["system_info"]["cpu_temperature"] == 45.0


def test_process_cputemp_none_when_no_valid_means(
    coordinator: TrueNASCoordinator,
) -> None:
    """An empty means dict leaves cpu_temperature as None."""
    coord = coordinator
    coord.ds = {"system_info": {}}
    coord._process_cputemp({"aggregations": {"mean": {}}})
    assert coord.ds["system_info"]["cpu_temperature"] is None


def test_process_memory_stat_computes_usage_percent(
    coordinator: TrueNASCoordinator,
) -> None:
    """Memory total/free/usage-percent are all derived from physmem and available."""
    coord = coordinator
    coord.ds = {"system_info": {"physmem": 1000}}
    coord._process_memory_stat(
        {"legend": ["available"], "aggregations": {"mean": {"available": 250.0}}}
    )
    assert coord.ds["system_info"]["memory-total_value"] == 1000
    assert coord.ds["system_info"]["memory-free_value"] == 250
    assert coord.ds["system_info"]["memory-usage_percent"] == 75


def test_handle_unknown_stat_logs_once_and_detects_near_miss(
    caplog: pytest.LogCaptureFixture, coordinator: TrueNASCoordinator
) -> None:
    """A repeated unknown stat name is only logged once, not on every call."""
    coord = coordinator
    coord.host = "truenas.local"
    coord._unknown_system_stat_names = set()
    with caplog.at_level("DEBUG"):
        coord._handle_unknown_stat("cpu_usage")
        coord._handle_unknown_stat("cpu_usage")
    assert caplog.text.count("unknown system stat graph name") == 1


def test_process_system_stat_interface_updates_rx_tx(
    coordinator: TrueNASCoordinator,
) -> None:
    """Valid received/sent means update the interface's rx/tx to positive values."""
    coord = coordinator
    coord.ds = {"interface": {"eth0": {}}}
    item = {
        "legend": ["received", "sent"],
        "aggregations": {"mean": {"received": 100.0, "sent": 50.0}},
    }
    coord._process_system_stat_interface(item, "eth0")
    assert coord.ds["interface"]["eth0"]["rx"] > 0
    assert coord.ds["interface"]["eth0"]["tx"] > 0


def test_process_system_stat_interface_zeroes_on_invalid_legend(
    coordinator: TrueNASCoordinator,
) -> None:
    """A non-list legend zeroes the interface's rx/tx instead of raising."""
    coord = coordinator
    coord.ds = {"interface": {"eth0": {}}}
    coord._process_system_stat_interface({"legend": "not-a-list"}, "eth0")
    assert coord.ds["interface"]["eth0"]["rx"] == 0.0
    assert coord.ds["interface"]["eth0"]["tx"] == 0.0


def test_process_system_stat_interface_zeroes_when_mean_not_dict(
    coordinator: TrueNASCoordinator,
) -> None:
    """A non-dict aggregations.mean zeroes the interface's rx/tx instead of raising."""
    coord = coordinator
    coord.ds = {"interface": {"eth0": {}}}
    item = {
        "legend": ["received", "sent"],
        "aggregations": {"mean": "not-a-dict"},
    }
    coord._process_system_stat_interface(item, "eth0")
    assert coord.ds["interface"]["eth0"]["rx"] == 0.0
    assert coord.ds["interface"]["eth0"]["tx"] == 0.0


async def test_get_systemstats_returns_early_without_graph_names(
    coordinator: TrueNASCoordinator,
) -> None:
    """No selectable graph names (all in cooldown) skips the API query entirely."""
    coord = coordinator
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


async def test_get_systemstats_returns_when_fetch_yields_no_graphs(
    coordinator: TrueNASCoordinator,
) -> None:
    """A None graph-fetch response leaves system_info untouched."""
    coord = coordinator
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


async def test_get_systemstats_processes_returned_graphs(
    coordinator: TrueNASCoordinator,
) -> None:
    """Graphs returned by the API are processed into system_info values."""
    coord = coordinator
    coord.ds = {"interface": {}, "system_info": {}}
    coord._is_virtual = True
    coord._systemstats_errored = {}
    coord.config_entry = MagicMock()
    coord.config_entry.options = {}
    coord.api = MagicMock()
    coord.api.query = AsyncMock(return_value=[{"name": "load"}])
    await coord.get_systemstats()
    assert coord.ds["system_info"]["load_shortterm"] == 0.0
