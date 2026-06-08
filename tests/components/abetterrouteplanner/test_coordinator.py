"""Tests for the telemetry coordinator + SSE consumer loop.

Mocks at the ``AbrpTelemetryClient.stream`` boundary (NOT raw SSE bytes).
``apply_frame`` merge tests push synthesized ``OutputPointWithVehicleId``
dicts directly through the coordinator.
"""

from collections.abc import Mapping
from http import HTTPStatus
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientResponseError
import pytest

from homeassistant.components.abetterrouteplanner import (
    coordinator as coordinator_module,
)
from homeassistant.components.abetterrouteplanner.api import AbrpApiError, AbrpAuthError
from homeassistant.components.abetterrouteplanner.const import signal_new_metric
from homeassistant.components.abetterrouteplanner.coordinator import (
    AbrpTelemetryCoordinator,
    AbrpVehiclesCoordinator,
    _run_sse_loop,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .conftest import MOCK_VEHICLE_ID, build_telemetry_frame

from tests.common import MockConfigEntry


@pytest.fixture(name="oauth_session")
def oauth_session_fixture() -> MagicMock:
    """A ``MagicMock(spec=OAuth2Session)`` with a quiet refresh path.

    ``async_ensure_token_valid`` is an ``AsyncMock`` returning ``None`` so
    the SSE loop's pre-connect refresh call succeeds without doing real
    HTTP. ``token`` exposes a synthetic access_token so the loop can read
    it when constructing the ``AbrpTelemetryClient``.
    """
    session = MagicMock(spec=OAuth2Session)
    session.async_ensure_token_valid = AsyncMock()
    session.token = {"access_token": "test-tok"}
    return session


@pytest.fixture(name="telemetry_coordinator")
def telemetry_coordinator_fixture(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
) -> AbrpTelemetryCoordinator:
    """A bare telemetry coordinator with no SSE wire attached.

    Wires only what ``apply_frame`` exercises (data store +
    ``async_set_updated_data``). The real coordinator constructor takes a
    websession + token; if the constructor signature changes, the test will
    fail loudly with a TypeError pointing at this fixture.
    """
    config_entry_with_vehicles.add_to_hass(hass)
    return AbrpTelemetryCoordinator(hass, config_entry_with_vehicles)


# ---------- apply_frame partial-update semantics ---------------------------


async def test_apply_frame_stores_new_vehicle(
    telemetry_coordinator: AbrpTelemetryCoordinator,
) -> None:
    """An apply_frame for an unknown vehicle stores the frame as-is."""
    frame = build_telemetry_frame(1, soc=0.85, power=23300.0, voltage=704.0)

    telemetry_coordinator.apply_frame(frame)

    assert telemetry_coordinator.data == {1: frame}


async def test_apply_frame_overlays_unchanged_fields(
    telemetry_coordinator: AbrpTelemetryCoordinator,
) -> None:
    """A second frame merges into the first — omitted keys retain prior values.

    Wire frames are deltas; replacing instead of merging would zero out
    unchanged metrics every event. This is the core merge invariant.
    """
    first = build_telemetry_frame(1, soc=0.85, power=23300.0, voltage=704.0)
    telemetry_coordinator.apply_frame(first)

    delta = build_telemetry_frame(1, power=5000.0)
    telemetry_coordinator.apply_frame(delta)

    merged = telemetry_coordinator.data[1]
    assert merged["soc"] == {"frac": 0.85}
    assert merged["power"] == {"w": 5000.0}
    assert merged["voltage"] == {"v": 704.0}


async def test_apply_frame_isolates_per_vehicle_state(
    telemetry_coordinator: AbrpTelemetryCoordinator,
) -> None:
    """Frames for different vehicles never bleed into each other's state."""
    telemetry_coordinator.apply_frame(build_telemetry_frame(1, soc=0.85))
    telemetry_coordinator.apply_frame(build_telemetry_frame(2, power=1000.0))

    assert telemetry_coordinator.data[1]["soc"] == {"frac": 0.85}
    assert "power" not in telemetry_coordinator.data[1]
    assert telemetry_coordinator.data[2]["power"] == {"w": 1000.0}
    assert "soc" not in telemetry_coordinator.data[2]


# ---------- apply_frame null-filter ----------------------------------------


async def test_apply_frame_skips_top_level_null(
    telemetry_coordinator: AbrpTelemetryCoordinator,
) -> None:
    """A top-level null leaf in a delta is treated as "no update for this metric".

    Regression for the user-reported "all sensors greyed out" bug: a frame
    ``{"power": null}`` must NOT overwrite the previously-merged
    ``{"power": {"w": 5000}}`` with ``None``. Null leaves mean "no update
    for this metric in this delta" — equivalent to the key being omitted.
    """
    telemetry_coordinator.apply_frame(build_telemetry_frame(1, power=5000.0))
    telemetry_coordinator.apply_frame({"vehicleId": 1, "power": None})

    assert telemetry_coordinator.data[1]["power"] == {"w": 5000.0}


async def test_apply_frame_skips_all_null_inner_dict(
    telemetry_coordinator: AbrpTelemetryCoordinator,
) -> None:
    """An inner dict whose leaves are all null is treated as no-update.

    After null-filtering ``{"w": null}`` becomes ``{}`` which is the
    "no metric in this delta" sentinel; the prior good value must survive.
    """
    telemetry_coordinator.apply_frame(build_telemetry_frame(1, power=5000.0))
    telemetry_coordinator.apply_frame({"vehicleId": 1, "power": {"w": None}})

    assert telemetry_coordinator.data[1]["power"] == {"w": 5000.0}


async def test_apply_frame_skips_empty_inner_dict(
    telemetry_coordinator: AbrpTelemetryCoordinator,
) -> None:
    """An empty inner dict is treated as no-update (prior value retained)."""
    telemetry_coordinator.apply_frame(build_telemetry_frame(1, power=5000.0))
    telemetry_coordinator.apply_frame({"vehicleId": 1, "power": {}})

    assert telemetry_coordinator.data[1]["power"] == {"w": 5000.0}


async def test_apply_frame_deep_merges_mixed_null_inner(
    telemetry_coordinator: AbrpTelemetryCoordinator,
) -> None:
    """Mixed-null inner: non-null leaves are merged, null leaves preserve prior.

    Frame B carries ``{"power": {"w": null, "time": T2}}`` over prior
    ``{"power": {"w": 50000, "time": T1}}``. After the deep-merge ``w`` is
    preserved at ``50000`` (null leaf → no update) while ``time`` is
    updated to ``T2``. Same shape generalises to the 15+ additional
    leaves under the same ``WithTimeAndProvider`` envelope.
    """
    telemetry_coordinator.apply_frame(
        {"vehicleId": 1, "power": {"w": 50000.0, "time": "T1"}}
    )
    telemetry_coordinator.apply_frame(
        {"vehicleId": 1, "power": {"w": None, "time": "T2"}}
    )

    assert telemetry_coordinator.data[1]["power"] == {"w": 50000.0, "time": "T2"}


async def test_apply_frame_null_isolation_across_vehicles(
    telemetry_coordinator: AbrpTelemetryCoordinator,
) -> None:
    """A null-leaf frame for vehicle A does not touch vehicle B's merged state."""
    telemetry_coordinator.apply_frame(build_telemetry_frame(1, soc=0.85))
    telemetry_coordinator.apply_frame(build_telemetry_frame(2, power=1000.0))

    telemetry_coordinator.apply_frame({"vehicleId": 1, "power": None})

    assert telemetry_coordinator.data[1]["soc"] == {"frac": 0.85}
    assert "power" not in telemetry_coordinator.data[1]
    assert telemetry_coordinator.data[2]["power"] == {"w": 1000.0}


async def test_apply_frame_overwrites_scalar_prior_with_new_inner_dict(
    telemetry_coordinator: AbrpTelemetryCoordinator,
) -> None:
    """A scalar prior at the same key is overwritten by the new inner dict.

    Pins the documented overwrite branch in ``apply_frame``.
    The wire is consistent per metric (dict-vs-scalar shape doesn't change
    mid-stream); a scalar prior at the key would be a contract violation
    from upstream. The intentional behaviour is to DROP the scalar and
    adopt the new inner dict rather than attempt a structural merge —
    structural merge against a scalar would either raise or pollute the
    snapshot with garbage shape.

    Synthetic prior: the production wire never produces this, but the
    branch is load-bearing if upstream ever ships a regression. Direct
    mutation of ``coordinator.data`` builds the scalar prior without
    requiring a wire payload that the integration would otherwise reject.
    """
    telemetry_coordinator.data = {1: {"power": "not-a-dict"}}

    telemetry_coordinator.apply_frame({"vehicleId": 1, "power": {"w": 1234.0}})

    assert telemetry_coordinator.data[1]["power"] == {"w": 1234.0}


async def test_apply_frame_accepts_mapping_with_none_leaves(
    telemetry_coordinator: AbrpTelemetryCoordinator,
) -> None:
    """A wire-shape ``Mapping`` with ``None`` leaves is accepted and merged.

    The widened parameter type (``Mapping[str, Any]``) reflects that the
    one-shot JSON poll and the SSE wire both deliver dicts with optional
    null leaves the ``OutputPointWithVehicleId`` TypedDict doesn't admit.
    The filter inside ``apply_frame`` does the null-stripping; the
    annotation merely matches the reality of what callers pass in.

    Pinning behaviour: a frame with ``None`` leaves at multiple levels
    must merge cleanly with the prior good state instead of failing a
    TypedDict-shape contract.
    """
    telemetry_coordinator.apply_frame(build_telemetry_frame(1, soc=0.5))

    raw_wire_frame: Mapping[str, Any] = {
        "vehicleId": 1,
        "soc": None,
        "power": {"w": None, "time": None},
        "voltage": {"v": 700.0},
    }
    telemetry_coordinator.apply_frame(raw_wire_frame)

    assert telemetry_coordinator.data[1]["soc"] == {"frac": 0.5}
    assert "power" not in telemetry_coordinator.data[1]
    assert telemetry_coordinator.data[1]["voltage"] == {"v": 700.0}


# ---------- apply_frame per-block staleness rejection ----------------
#
# Per-block ``time``-based rejection of stale-on-arrival rollup blocks.
# User-reported production bug: HA recorder emits the
# ``not monotonically increasing`` warning on the odometer sensor's
# ``TOTAL_INCREASING`` state_class after every SSE reconnect, because
# ABRP backfills a heterogeneous rollup frame whose ``odometer`` block
# carries an older measurement-time than the in-memory fresh value. The
# fix is a per-block (NOT whole-frame) comparison of the incoming and
# stored ISO-8601 ``time``; an older block skips the merge AND the
# per-key ``last_reported_at`` / ``last_provider`` updates.

# Helper symbol resolved via getattr so this test file imports cleanly
# even when ``_parse_block_time`` is later renamed. The placeholder
# returns a fresh ``object`` (NOT ``None``) so any helper-level
# parametrize row that depends on the real implementation fails loudly
# rather than silently passing on the sentinel.
_parse_block_time = getattr(
    coordinator_module, "_parse_block_time", lambda block: object()
)

_T_FRESH = "2026-05-25T05:30:17Z"
_T_OLD = "2026-05-24T07:18:19Z"


@pytest.mark.parametrize(
    ("wire_key", "registry_key", "fresh_inner", "stale_inner"),
    [
        pytest.param(
            "odometer",
            "odometer",
            {"m": 33000000},
            {"m": 32500000},
            id="odometer_symmetric",
        ),
        pytest.param(
            "estimatedBatteryRange",
            "range",
            {"m": 33000000},
            {"m": 32500000},
            id="range_asymmetric",
        ),
        pytest.param(
            "chargingState",
            "charging_state",
            {"state": "CHARGING_AC"},
            {"state": "NOT_CHARGING"},
            id="charging_state_asymmetric_enum",
        ),
    ],
)
async def test_apply_frame_rejects_stale_block_rollup(
    telemetry_coordinator: AbrpTelemetryCoordinator,
    wire_key: str,
    registry_key: str,
    fresh_inner: dict[str, Any],
    stale_inner: dict[str, Any],
) -> None:
    """Stale block rejected — across symmetric AND asymmetric key pairs.

    User-reported flow: SSE reconnect → ABRP sends a rollup frame
    mixing fresh and stale per-metric blocks. Without stale-skipping,
    ``apply_frame`` would overwrite the fresh value with the stale
    rollup and HA recorder would log the ``not monotonically increasing``
    warning. The stale block is skipped — merge, ``last_reported_at``,
    AND ``last_provider`` all preserve the prior fresher state.


    ``STAMPED_VALUE_FNS`` has two shape-classes — **symmetric**
    (``wire_key == registry_key``: odometer, soc, power, voltage, soe,
    soh, location) and **asymmetric** (``wire_key != registry_key``:
    ``estimatedBatteryRange``/``range``,
    ``calibratedRefCons``/``calibrated_ref_cons``,
    ``batteryCapacity``/``battery_capacity``,
    ``batteryTemperature``/``battery_temperature``,
    ``chargingState``/``charging_state``).

    The two shape-classes diverge under the staleness gate's stamp
    loop: ``stale_keys`` is built from ``frame.items()`` (= wire keys)
    while ``STAMPED_VALUE_FNS`` iterates ``(registry_key, wire_key,
    value_fn)``. A guard written as ``if registry_key in stale_keys:
    continue`` silently bypasses the stale-skip on all asymmetric
    metrics (registry-key namespace doesn't match wire-key stale set)
    → ``last_reported_at`` + ``last_provider`` get bumped with
    backdated values. The symmetric row passes trivially; the
    asymmetric rows are the asymmetric-stale-skip regression pin: an
    asymmetric registry-key vs wire-key mismatch in any of the
    asymmetric metrics surfaces as backdated stamps. The
    ``charging_state`` enum row exercises the same gate for a
    categorical (non-numeric) leaf shape.
    """
    vid = 1
    fresh_frame: dict[str, Any] = {
        "vehicleId": vid,
        wire_key: {**fresh_inner, "time": _T_FRESH, "provider": "TLM_API"},
    }
    stale_frame: dict[str, Any] = {
        "vehicleId": vid,
        wire_key: {**stale_inner, "time": _T_OLD, "provider": "DERIVED"},
    }

    telemetry_coordinator.apply_frame(fresh_frame)
    fresh_stamp = telemetry_coordinator.last_reported_at[vid][registry_key]
    fresh_provider = telemetry_coordinator.last_provider[vid][registry_key]

    telemetry_coordinator.apply_frame(stale_frame)

    block = telemetry_coordinator.data[vid][wire_key]
    assert {key: block[key] for key in fresh_inner} == fresh_inner
    assert block["time"] == _T_FRESH
    # last_reported_at MUST preserve the fresh stamp — stale frame
    # observed the metric but didn't carry newer info, so the
    # user-visible "when did upstream last surface this" stays pinned
    # to the fresh measurement, not bumped to now.
    assert telemetry_coordinator.last_reported_at[vid][registry_key] == fresh_stamp
    # last_provider preserves TLM_API; stale-skipped block does NOT
    # overwrite with DERIVED.
    assert telemetry_coordinator.last_provider[vid][registry_key] == fresh_provider


async def test_apply_frame_equal_time_adopts_incoming(
    telemetry_coordinator: AbrpTelemetryCoordinator,
) -> None:
    """Equal incoming/stored ``time`` is idempotent — incoming adopted.

    Strict less-than is the staleness boundary; equal-time means
    "same measurement, no new information." Re-applying writes through
    harmlessly (same value, same stamp).
    """
    vid = 1
    block = {"m": 100, "time": _T_FRESH}
    frame: dict[str, Any] = {"vehicleId": vid, "odometer": dict(block)}

    telemetry_coordinator.apply_frame(frame)
    telemetry_coordinator.apply_frame({"vehicleId": vid, "odometer": dict(block)})

    assert telemetry_coordinator.data[vid]["odometer"] == block


async def test_apply_frame_first_ever_block_adopts_regardless_of_time(
    telemetry_coordinator: AbrpTelemetryCoordinator,
) -> None:
    """First-ever block for a vehicle is adopted no matter how old.

    No prior merged state means nothing to compare against — the
    rollup is the most-recent information we have. Adopt
    unconditionally.
    """
    vid = 1
    rollup: dict[str, Any] = {
        "vehicleId": vid,
        "odometer": {"m": 100, "time": _T_OLD},
    }

    telemetry_coordinator.apply_frame(rollup)

    assert telemetry_coordinator.data[vid]["odometer"] == {"m": 100, "time": _T_OLD}


@pytest.mark.parametrize(
    ("fresh_time", "old_time"),
    [
        pytest.param("2026-05-25T05:30:17Z", "2026-05-25T05:30:16Z", id="seconds_Z"),
        pytest.param(
            "2026-05-24T09:05:05.446Z",
            "2026-05-24T09:05:05.445Z",
            id="millis_Z",
        ),
    ],
)
async def test_apply_frame_parses_both_iso_shapes_for_staleness(
    telemetry_coordinator: AbrpTelemetryCoordinator,
    fresh_time: str,
    old_time: str,
) -> None:
    """Both wire ISO-8601 shapes (with/without millis) drive stale rejection.

    User-captured rollup carries seconds-Z (``2026-05-25T05:30:17Z``)
    AND millisecond-Z (``2026-05-24T09:05:05.446Z``) in a SINGLE frame.
    The HA stdlib ``parse_datetime`` handles each via ciso8601 fast
    path / regex fallback — both must round-trip cleanly through
    ``_parse_block_time`` and gate the per-block staleness check.

    both ISO
    shapes are symmetric inputs to the same parse boundary; cover each
    independently so a one-format-only impl fails the other row.
    """
    vid = 1
    fresh_frame: dict[str, Any] = {
        "vehicleId": vid,
        "odometer": {"m": 200, "time": fresh_time},
    }
    old_frame: dict[str, Any] = {
        "vehicleId": vid,
        "odometer": {"m": 100, "time": old_time},
    }

    telemetry_coordinator.apply_frame(fresh_frame)
    telemetry_coordinator.apply_frame(old_frame)

    odometer_block = telemetry_coordinator.data[vid]["odometer"]
    assert odometer_block["m"] == 200
    assert odometer_block["time"] == fresh_time


async def test_apply_frame_stale_skip_does_not_double_dispatch(
    hass: HomeAssistant,
    telemetry_coordinator: AbrpTelemetryCoordinator,
) -> None:
    """Stale block does not re-fire ``signal_new_metric`` (defensive pin).

    First frame fires the dispatcher signal once; the production sensor
    platform's listener then calls :meth:`mark_metric_seen` so the
    pair lands in ``_presence_seen`` (unit test simulates that wiring
    manually). A subsequent stale rollup MUST NOT re-fire the signal:
    the pair is already in ``_presence_seen`` and the merge itself is
    stale-skipped. Pinned defensively against a future refactor that
    decouples seen-state from dispatch.

    assert the
    "exactly one dispatch" invariant after the FIRST frame, then
    trigger the stale frame and re-assert. Without the pre-trigger
    assertion, a never-firing dispatcher would appear "stable" through
    both frames.
    """
    vid = 1

    def _odometer_pred(frame: Mapping[str, Any]) -> float | None:
        block = frame.get("odometer")
        if not isinstance(block, dict):
            return None
        m = block.get("m")
        return m if isinstance(m, (int, float)) else None

    telemetry_coordinator.register_presence_predicates({"odometer": _odometer_pred})

    signal = signal_new_metric(telemetry_coordinator.config_entry.entry_id)
    dispatch_calls: list[tuple[int, str]] = []

    @callback
    def _record(vehicle_id: int, metric_key: str) -> None:
        dispatch_calls.append((vehicle_id, metric_key))

    unsub = async_dispatcher_connect(hass, signal, _record)
    try:
        fresh_frame: dict[str, Any] = {
            "vehicleId": vid,
            "odometer": {"m": 33000000, "time": _T_FRESH},
        }
        stale_frame: dict[str, Any] = {
            "vehicleId": vid,
            "odometer": {"m": 32500000, "time": _T_OLD},
        }

        telemetry_coordinator.apply_frame(fresh_frame)
        await hass.async_block_till_done()
        assert dispatch_calls == [(vid, "odometer")]
        # Simulate the sensor platform's listener marking the metric
        # seen after first dispatch (production: listener invokes
        # ``mark_metric_seen`` after ``async_add_entities`` so a
        # transient skip cannot permanently suppress future
        # dispatches).
        telemetry_coordinator.mark_metric_seen(vid, "odometer")

        telemetry_coordinator.apply_frame(stale_frame)
        await hass.async_block_till_done()
        assert dispatch_calls == [(vid, "odometer")]
    finally:
        unsub()


@pytest.mark.parametrize(
    "block",
    [
        pytest.param({"time": "T2"}, id="string_unparsable_marker"),
        pytest.param({"time": 12345}, id="int_marker_existing_fixture_shape"),
        pytest.param({}, id="no_time_key"),
        pytest.param(
            {"time": "2026-13-01T00:00:00Z"}, id="invalid_iso_raises_ValueError"
        ),
        pytest.param({"time": "2026-02-30T00:00:00Z"}, id="invalid_iso_day_overflow"),
        pytest.param({"time": "2026-05-25T05:30:17"}, id="naive_iso_returns_None"),
        pytest.param({"time": ""}, id="empty_string_returns_None"),
        pytest.param({"time": "   "}, id="whitespace_string_returns_None"),
    ],
)
def test_parse_block_time_returns_none_for_unparsable_or_naive(
    block: Mapping[str, Any],
) -> None:
    """``_parse_block_time`` returns None on every non-tz-aware-ISO shape.

    14 existing fixtures across the suite use opaque ``int`` /
    non-ISO-string ``time`` markers; defensive fall-through to None is
    load-bearing for backwards-compat. Mitigations:
    well-formed-regex invalid-datetime
    (e.g. month=13, day=30) propagates ``ValueError`` from
    ``parse_datetime``'s ``dt.datetime(**kws)`` constructor — caught
    and returned as None; tz-naive parsed datetimes return None so the
    comparison site never sees a naive vs aware ``TypeError``.

    walks every
    None-return failure mode of the helper independently so a partial
    impl (e.g. missing the ``ValueError`` catch) fails ONLY the
    invalid-iso rows.
    """
    assert _parse_block_time(block) is None


async def test_apply_frame_unparsable_time_falls_through_to_adopt(
    telemetry_coordinator: AbrpTelemetryCoordinator,
) -> None:
    """Unparsable ``time`` on either side falls through to merge.

    Single ``apply_frame``-level row pinning the helper-to-apply_frame
    wiring for the fall-through path. The helper-level parametrize
    above pins each parse-failure shape directly; this row confirms
    that a None return from the helper means "no stale-gate" → merge
    adopts incoming.
    """
    vid = 1
    first_frame: dict[str, Any] = {
        "vehicleId": vid,
        "odometer": {"m": 100, "time": "garbage"},
    }
    second_frame: dict[str, Any] = {
        "vehicleId": vid,
        "odometer": {"m": 200, "time": "still_garbage"},
    }

    telemetry_coordinator.apply_frame(first_frame)
    telemetry_coordinator.apply_frame(second_frame)

    assert telemetry_coordinator.data[vid]["odometer"]["m"] == 200


# ---------- register_presence_predicates merge semantics -----------


async def test_register_presence_predicates_merges_with_prior(
    telemetry_coordinator: AbrpTelemetryCoordinator,
) -> None:
    """Two platforms registering disjoint keys both survive in the predicate dict.

    Registration uses merge semantics
    (``self._presence_predicates.update(predicates)``), not overwrite
    (``self._presence_predicates = dict(predicates)``). With the
    two-platform forwarding (sensor + device_tracker), each
    platform independently registers its own predicate keys; an
    overwrite implementation would silently drop the first platform's
    predicates and break lazy creation for those metrics.

    Structural assertion on ``_presence_predicates``: the property under
    test is a registration-topology fact (which keys live in the dict
    after two registrations), not a behavioural state-machine assertion.

    Will-fail oracle under current overwrite semantics: only the
    LAST-registered key (``"location"``) survives; the assertion's
    expected ``{"soc", "location"}`` set finds ``{"location"}``.
    """

    def _soc_pred(frame: Mapping[str, Any]) -> float | None:
        soc = frame.get("soc")
        return soc.get("frac") if isinstance(soc, dict) else None

    def _location_pred(frame: Mapping[str, Any]) -> tuple[float, float] | None:
        loc = frame.get("location")
        if not isinstance(loc, dict):
            return None
        lat, lng = loc.get("lat"), loc.get("long")
        if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
            return lat, lng
        return None

    telemetry_coordinator.register_presence_predicates({"soc": _soc_pred})
    telemetry_coordinator.register_presence_predicates({"location": _location_pred})

    assert set(telemetry_coordinator._presence_predicates) == {"soc", "location"}


async def test_register_presence_predicates_idempotent_on_same_key(
    telemetry_coordinator: AbrpTelemetryCoordinator,
) -> None:
    """Re-registering the same key overwrites — by design.

    A platform may re-setup, so the LAST-registered callable for a given
    key wins: a platform unload+reload cleanly replaces its own predicates
    without leaking stale ones.
    """

    def _first(frame: Mapping[str, Any]) -> float | None:
        return 1.0

    def _second(frame: Mapping[str, Any]) -> float | None:
        return 2.0

    telemetry_coordinator.register_presence_predicates({"soc": _first})
    telemetry_coordinator.register_presence_predicates({"soc": _second})

    predicates = telemetry_coordinator._presence_predicates
    assert predicates["soc"] is _second


# ---------- async_seed_from_json_poll ---------------------------------------


async def test_async_seed_from_json_poll_happy_path(
    telemetry_coordinator: AbrpTelemetryCoordinator,
    mock_seed_responses: AsyncMock,
) -> None:
    """Successful one-shot poll for each vehicle populates ``coordinator.data``.

    Each per-vehicle response is stamped with ``vehicleId`` (path-scoped, not
    in body) and fed through ``apply_frame`` — same merge as the SSE consumer,
    so the seed inherits the null-aware deep-merge for free.
    """
    mock_seed_responses.responses[1] = {"soc": {"frac": 0.5}}
    mock_seed_responses.responses[2] = {"power": {"w": 5000.0}}

    await telemetry_coordinator.async_seed_from_json_poll([1, 2], "tok")

    assert telemetry_coordinator.data[1]["soc"] == {"frac": 0.5}
    assert telemetry_coordinator.data[2]["power"] == {"w": 5000.0}


async def test_async_seed_from_json_poll_partial_failure_does_not_block_others(
    telemetry_coordinator: AbrpTelemetryCoordinator,
    mock_seed_responses: AsyncMock,
) -> None:
    """One vehicle's seed failure must not block the others.

    Uses ``asyncio.gather(..., return_exceptions=True)`` semantics: the
    failing vehicle is dropped (no entry in ``coordinator.data``), the
    successful one is populated, no exception bubbles up from the
    coordinator method.
    """
    mock_seed_responses.responses[1] = {"soc": {"frac": 0.5}}
    mock_seed_responses.responses[2] = AbrpApiError("backend overloaded")

    await telemetry_coordinator.async_seed_from_json_poll([1, 2], "tok")

    assert telemetry_coordinator.data[1]["soc"] == {"frac": 0.5}
    assert 2 not in telemetry_coordinator.data


async def test_async_seed_from_json_poll_all_failures_swallowed(
    telemetry_coordinator: AbrpTelemetryCoordinator,
    mock_seed_responses: AsyncMock,
) -> None:
    """All vehicles failing leaves ``data`` empty and raises nothing.

    Seed is best-effort — SSE is the authoritative source. If every
    per-vehicle poll fails (e.g. ABRP-side outage), setup must continue and
    the SSE consumer must still spawn.
    """
    mock_seed_responses.responses[1] = AbrpAuthError("invalid session")
    mock_seed_responses.responses[2] = AbrpApiError("503")

    await telemetry_coordinator.async_seed_from_json_poll([1, 2], "tok")

    assert telemetry_coordinator.data == {}


# ---------- _run_sse_loop reconnect + backoff -------------------------------


async def test_sse_loop_backoff_sequence(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    oauth_session: MagicMock,
) -> None:
    """Repeated stream failures sleep 5 → 10 → 30 → 60s and cap at 60s.

    Patches ``asyncio.sleep`` inside the coordinator module so the test
    completes in ms while still asserting the exact wait sequence the
    plan calls for.
    """
    config_entry_with_vehicles.add_to_hass(hass)
    coordinator = AbrpTelemetryCoordinator(hass, config_entry_with_vehicles)

    sleep_calls: list[float] = []

    async def _record_sleep(delay: float) -> None:
        sleep_calls.append(delay)
        if len(sleep_calls) >= 5:
            raise _StopLoop

    stream_mock = MagicMock(side_effect=AbrpApiError("boom"))

    with (
        patch(
            "homeassistant.components.abetterrouteplanner.coordinator.asyncio.sleep",
            new=_record_sleep,
        ),
        patch(
            "homeassistant.components.abetterrouteplanner.api.AbrpTelemetryClient.stream",
            stream_mock,
        ),
        pytest.raises(_StopLoop),
    ):
        await _run_sse_loop(
            hass, config_entry_with_vehicles, coordinator, oauth_session, [1]
        )

    assert sleep_calls == [5, 10, 30, 60, 60]


async def test_sse_loop_backoff_resets_after_successful_event(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    oauth_session: MagicMock,
) -> None:
    """Backoff resets to 5s after the loop receives at least one event.

    Driver: stream() raises, then a stream() yields one frame then exits
    (a normal drop), then raises again. The sleep before the second
    failure-loop must be 5s, not the next step in the prior backoff
    sequence — proving the reset.
    """
    config_entry_with_vehicles.add_to_hass(hass)
    coordinator = AbrpTelemetryCoordinator(hass, config_entry_with_vehicles)

    sleep_calls: list[float] = []
    call_count = 0

    async def _one_event_then_exit() -> Any:
        yield build_telemetry_frame(1, soc=0.5)

    def _stream_factory(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal call_count
        call_count += 1
        if call_count in (1, 3):
            raise AbrpApiError("disconnected")
        return _one_event_then_exit()

    async def _record_sleep(delay: float) -> None:
        sleep_calls.append(delay)
        if len(sleep_calls) >= 2:
            raise _StopLoop

    with (
        patch(
            "homeassistant.components.abetterrouteplanner.coordinator.asyncio.sleep",
            new=_record_sleep,
        ),
        patch(
            "homeassistant.components.abetterrouteplanner.api.AbrpTelemetryClient.stream",
            side_effect=_stream_factory,
        ),
        pytest.raises(_StopLoop),
    ):
        await _run_sse_loop(
            hass, config_entry_with_vehicles, coordinator, oauth_session, [1]
        )

    assert sleep_calls == [5, 5]


# ---------- auth failure propagation ----------------------------------------


async def test_sse_loop_auth_error_marks_coordinator_for_reauth(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_sse_client: MagicMock,
    oauth_session: MagicMock,
) -> None:
    """An ``AbrpAuthError`` from stream surfaces as a reauth-triggering update error.

    The plan: HTTP 401 / `AbrpAuthError` → ``async_set_update_error`` with
    ``ConfigEntryAuthFailed`` → HA reauth pipeline picks it up → SSE task
    exits cleanly (no infinite backoff).
    """
    config_entry_with_vehicles.add_to_hass(hass)
    coordinator = AbrpTelemetryCoordinator(hass, config_entry_with_vehicles)

    mock_sse_client.side_effect = AbrpAuthError("invalid session")

    set_error_mock = MagicMock()
    with patch.object(coordinator, "async_set_update_error", new=set_error_mock):
        await _run_sse_loop(
            hass, config_entry_with_vehicles, coordinator, oauth_session, [1]
        )

    assert set_error_mock.called
    (err,), _ = set_error_mock.call_args
    assert isinstance(err, ConfigEntryAuthFailed)


# ---------- session refresh paths ------------------------------------------


async def test_sse_loop_refreshes_token_without_reauth(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_sse_client: MagicMock,
    oauth_session: MagicMock,
) -> None:
    """A successful pre-connect refresh keeps the loop running, no reauth flow.

    Proves ``session.async_ensure_token_valid`` is invoked
    before each connect attempt, swallows the silent-expiry case (token
    auto-rotated, no exception raised), and the consumer continues to
    accept events normally.
    """
    config_entry_with_vehicles.add_to_hass(hass)
    coordinator = AbrpTelemetryCoordinator(hass, config_entry_with_vehicles)

    async def _one_then_exit() -> Any:
        yield build_telemetry_frame(MOCK_VEHICLE_ID, soc=0.5)

    mock_sse_client.side_effect = lambda *_a, **_kw: _one_then_exit()

    async def _record_sleep(_delay: float) -> None:
        raise _StopLoop

    with (
        patch(
            "homeassistant.components.abetterrouteplanner.coordinator.asyncio.sleep",
            new=_record_sleep,
        ),
        pytest.raises(_StopLoop),
    ):
        await _run_sse_loop(
            hass,
            config_entry_with_vehicles,
            coordinator,
            oauth_session,
            [MOCK_VEHICLE_ID],
        )

    assert oauth_session.async_ensure_token_valid.called
    assert not hass.config_entries.flow.async_progress()


async def test_sse_loop_refresh_4xx_starts_reauth(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    oauth_session: MagicMock,
) -> None:
    """A 4xx from the OAuth token endpoint during refresh surfaces as reauth.

    ``async_ensure_token_valid`` raising ``ClientResponseError(401)`` must
    be caught and converted to a ``ConfigEntryAuthFailed`` update-error so
    the loop exits cleanly and HA's reauth pipeline takes over — no
    backoff sleep, no retry storm against a permanently-bad token.
    """
    config_entry_with_vehicles.add_to_hass(hass)
    coordinator = AbrpTelemetryCoordinator(hass, config_entry_with_vehicles)

    oauth_session.async_ensure_token_valid.side_effect = ClientResponseError(
        request_info=MagicMock(),
        history=(),
        status=HTTPStatus.UNAUTHORIZED,
        message="Unauthorized",
    )

    set_error_mock = MagicMock()

    async def _sleep_should_not_be_called(_delay: float) -> None:
        raise AssertionError("sleep called after 4xx refresh; expected clean exit")

    with (
        patch.object(coordinator, "async_set_update_error", new=set_error_mock),
        patch(
            "homeassistant.components.abetterrouteplanner.coordinator.asyncio.sleep",
            new=_sleep_should_not_be_called,
        ),
    ):
        await _run_sse_loop(
            hass,
            config_entry_with_vehicles,
            coordinator,
            oauth_session,
            [MOCK_VEHICLE_ID],
        )

    assert set_error_mock.called
    (err,), _ = set_error_mock.call_args
    assert isinstance(err, ConfigEntryAuthFailed)


class _StopLoop(Exception):
    """Raised from the patched ``asyncio.sleep`` to exit the SSE loop in tests."""


# ---------------------------------------------------------------------------
#  v2 catalog cache on AbrpVehiclesCoordinator
# ---------------------------------------------------------------------------
#
# Skip-on-miss design: the garage coordinator
# fetches the v2 catalog lazily-once on first ``_async_update_data`` via the
# new ``AbrpClient.async_get_catalog`` method, never refetches mid-session,
# and treats catalog-fetch failure as non-fatal (assign ``self._catalog = {}``
# + warning log + return v1 garage data).
#
# All three tests mock ``async_get_vehicles`` with ``return_value=[]`` so
# the current ``AbrpVehicle`` dataclass extension doesn't affect this test
# module's robustness — the enrichment loop iterates over zero raw records
# while the catalog-cache code path still exercises end-to-end.


async def test_garage_coordinator_loads_catalog_on_first_refresh(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    oauth_session: MagicMock,
) -> None:
    """First ``_async_update_data`` fetches the catalog; second refresh does NOT.

    Pins the lazy-once invariant: the catalog is fetched
    once per coordinator lifetime ("Reload of the config entry is the only
    refresh path; mid-session catalog updates on ABRP's side do NOT
    materialize new sensors until reload."). A regression that refetched
    on every poll cycle would surface here as ``call_count == 2`` after
    the second refresh.
    """
    config_entry_with_vehicles.add_to_hass(hass)
    coordinator = AbrpVehiclesCoordinator(
        hass, config_entry_with_vehicles, oauth_session
    )

    with (
        patch(
            "homeassistant.components.abetterrouteplanner.api.AbrpClient.async_get_vehicles",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "homeassistant.components.abetterrouteplanner.api.AbrpClient.async_get_catalog",
            create=True,
            new_callable=AsyncMock,
            return_value={},
        ) as mock_catalog,
    ):
        await coordinator._async_update_data()
        assert mock_catalog.call_count == 1, (
            "First refresh must trigger catalog fetch (lazy load on first refresh)"
        )

        await coordinator._async_update_data()
        assert mock_catalog.call_count == 1, (
            "Second refresh must NOT re-fetch catalog (lazy-once invariant)"
        )


@pytest.mark.parametrize(
    "catalog_error",
    [
        pytest.param(AbrpAuthError("HTTP 401"), id="auth_error"),
        pytest.param(AbrpApiError("HTTP 500"), id="api_error"),
        pytest.param(TimeoutError("budget exceeded"), id="timeout_error"),
    ],
)
async def test_garage_coordinator_catalog_fetch_failure_non_fatal(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    oauth_session: MagicMock,
    caplog: pytest.LogCaptureFixture,
    catalog_error: Exception,
) -> None:
    """Catalog-fetch failure (auth / api / timeout) is non-fatal — integration ships.

    The ``AbrpAuthError`` and ``AbrpApiError`` from
    ``async_get_catalog`` degrade the integration gracefully — the v1
    garage path is independent and still surfaces vehicles; only
    ``DeviceInfo.model`` falls back to the raw type code until reload.

    The ``timeout_error`` case is a **defense-in-depth regression-guard**.
    ``async_get_catalog`` wraps ``asyncio.TimeoutError`` as
    ``AbrpApiError`` at the client boundary, so under normal flow the
    coordinator never sees a naked TimeoutError on the catalog path.
    But if a future code path bypassed the wrapper (e.g. a new client
    method added without the same catch-band extension, or an outer
    timeout layer leaking a different ``TimeoutError`` subclass), the
    coordinator's catch band must still trip the fail-soft path rather
    than crash the entire refresh. Belt-and-suspenders.

    Three behavioural pins:

    * ``_async_update_data`` returns a list (no raise propagated from
      catalog failure); the v1 garage path is unaffected.
    * Coordinator's ``_catalog`` cache is set to ``{}`` so the lazy-once
      gate sees the cache as initialised — subsequent refreshes don't
      retry until config-entry reload.
    * A warning is logged so users can correlate the degraded UI surface
      with the upstream fault.

    Auth-on-catalog vs auth-on-garage is intentionally asymmetric: a
    garage 401 still triggers reauth (separate code path); a catalog
    401 is fail-soft because the catalog endpoint may rate-limit
    independently of the per-user garage endpoint.
    """
    config_entry_with_vehicles.add_to_hass(hass)
    coordinator = AbrpVehiclesCoordinator(
        hass, config_entry_with_vehicles, oauth_session
    )

    with (
        caplog.at_level(logging.WARNING),
        patch(
            "homeassistant.components.abetterrouteplanner.api.AbrpClient.async_get_vehicles",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "homeassistant.components.abetterrouteplanner.api.AbrpClient.async_get_catalog",
            create=True,
            new_callable=AsyncMock,
            side_effect=catalog_error,
        ),
    ):
        result = await coordinator._async_update_data()

    assert result == []
    assert coordinator._catalog == {}
    assert any("catalog" in record.message.lower() for record in caplog.records), (
        "Expected a warning log mentioning the catalog fetch failure"
    )


# ---------------------------------------------------------------------------
# Provider attribute stamp loop
# ---------------------------------------------------------------------------
#
# The coordinator stamps a per-vehicle, per-metric ``last_provider`` map
# in :meth:`AbrpTelemetryCoordinator.apply_frame` alongside the existing
# ``last_reported_at`` map. Sticky-on-omission: a metric block present
# without a usable provider (absent / non-string / empty-string) MUST
# retain the prior provider value rather than blank it. Empty-string is
# symmetrically rejected on both live and restore paths so the
# integration treats ``""`` consistently as malformed input.
#
# Constants pulled lazily via ``getattr`` so the test file loads cleanly
# even when the ``last_provider`` slot is later renamed on the
# coordinator.


# Sentinel for "key absent from provider position", distinct from a value
# of ``None`` (which would mean "key present with value None").
_NO_PROVIDER_KEY = object()


def _last_provider(
    coord: AbrpTelemetryCoordinator,
) -> dict[int, dict[str, str]]:
    """Read ``coord.last_provider`` with a graceful default.

    Before the new coordinator slot is materialised, the attribute does
    not exist yet. ``getattr`` with an empty-dict default keeps the test
    file importable while still failing each test's value-assertion with a
    crisp ``{} != {expected}`` mismatch rather than ``AttributeError``.
    """
    return getattr(coord, "last_provider", {})


def _voltage_frame(
    *,
    vehicle_id: int = MOCK_VEHICLE_ID,
    volts: float = 400.0,
    provider: object = _NO_PROVIDER_KEY,
) -> dict[str, Any]:
    """Construct an unmerged ``voltage`` frame; optionally embed ``provider``.

    Wire shape per ``~/abrp/abrp/spec/api/common/tlm.yaml`` ``WithTimeAndProvider``:
    provider is a NotRequired key inside each per-metric block. Sentinel
    dispatch on ``provider``
    encodes "key absent" without conflating with the literal value ``None``.
    """
    block: dict[str, Any] = {"v": volts}
    if provider is not _NO_PROVIDER_KEY:
        block["provider"] = provider
    return {"vehicleId": vehicle_id, "voltage": block}


def _location_frame(
    *,
    vehicle_id: int = MOCK_VEHICLE_ID,
    lat: float = 37.7749,
    lng: float = -122.4194,
    provider: object = _NO_PROVIDER_KEY,
) -> dict[str, Any]:
    """Construct an unmerged ``location`` frame; optionally embed ``provider``.

    Mirrors :func:`_voltage_frame` for the device_tracker key in
    ``STAMPED_VALUE_FNS``. Pins the cross-platform contract: the same stamp
    loop covers sensor metrics AND the location key.
    """
    block: dict[str, Any] = {"lat": lat, "long": lng}
    if provider is not _NO_PROVIDER_KEY:
        block["provider"] = provider
    return {"vehicleId": vehicle_id, "location": block}


# --- T1 -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("registry_key", "wire_key", "inner"),
    [
        pytest.param("soc", "soc", {"frac": 0.85}, id="soc"),
        pytest.param("power", "power", {"w": 12000.0}, id="power"),
        pytest.param("voltage", "voltage", {"v": 400.0}, id="voltage"),
        pytest.param("soe", "soe", {"wh": 50000.0}, id="soe"),
        pytest.param("odometer", "odometer", {"m": 100000.0}, id="odometer"),
        pytest.param(
            "calibrated_ref_cons",
            "calibratedRefCons",
            {"wh_per_km": 175.0},
            id="calibrated_ref_cons",
        ),
        pytest.param(
            "battery_capacity",
            "batteryCapacity",
            {"wh": 75000.0},
            id="battery_capacity",
        ),
        pytest.param("soh", "soh", {"frac": 0.95}, id="soh"),
        pytest.param(
            "range",
            "estimatedBatteryRange",
            {"m": 300000.0},
            id="range",
        ),
        pytest.param(
            "battery_temperature",
            "batteryTemperature",
            {"c": 22.5},
            id="battery_temperature",
        ),
        pytest.param(
            "charging_state",
            "chargingState",
            {"state": "CHARGING_AC"},
            id="charging_state",
        ),
        pytest.param(
            "location",
            "location",
            {"lat": 37.7749, "long": -122.4194},
            id="location",
        ),
    ],
)
async def test_apply_frame_stamps_provider_per_metric(
    telemetry_coordinator: AbrpTelemetryCoordinator,
    registry_key: str,
    wire_key: str,
    inner: dict[str, Any],
) -> None:
    """``apply_frame`` stamps ``last_provider[vid][registry_key]`` for every metric.

    Full-coverage parametrize across the 11 sensor keys plus the
    device_tracker location key — the union of every metric that
    appears in ``STAMPED_VALUE_FNS``. Distinguishes the **registry
    key** (the internal slot name used by the value_fn registry,
    snake_case for sensors) from the **wire key** (what the SSE
    server emits, sometimes camelCase per the v2 wire spec).

    Five rows have asymmetric naming and exercise the wire-key lookup
    in ``_extract_provider``:

    | registry_key            | wire_key                |
    |-------------------------|-------------------------|
    | ``calibrated_ref_cons`` | ``calibratedRefCons``   |
    | ``battery_capacity``    | ``batteryCapacity``     |
    | ``range``               | ``estimatedBatteryRange`` |
    | ``battery_temperature`` | ``batteryTemperature``  |
    | ``charging_state``      | ``chargingState``       |

    The other 7 rows have ``registry_key == wire_key`` (no naming
    flip — sensor keys that happened to match the v2 wire spec
    verbatim, plus location).

    The bug a prior tester-side miss let through: a
    ``_extract_provider(frame, registry_key)`` that uses the snake_case
    key for ``frame.get(...)`` always misses the 4 camelCase rows →
    no stamp lands → the user-visible attribute is permanently absent
    on those sensors regardless of wire payload. The expanded
    parametrize exposes it via 4 cleanly-targeted RED cases.

    the
    "stamp lands per metric" contract is symmetric across every key
    in the registry; the parametrize must walk every key, not just a
    representative pair.
    """
    frame: dict[str, Any] = {
        "vehicleId": MOCK_VEHICLE_ID,
        wire_key: {**inner, "provider": "RIVIAN_STREAM"},
    }

    telemetry_coordinator.apply_frame(frame)

    assert _last_provider(telemetry_coordinator)[MOCK_VEHICLE_ID][registry_key] == (
        "RIVIAN_STREAM"
    )


# --- T2 -------------------------------------------------------------------


async def test_apply_frame_provider_overwrites_on_change(
    telemetry_coordinator: AbrpTelemetryCoordinator,
) -> None:
    """A subsequent frame with a different provider wins; last-frame semantics.

    The providers don't normally flip mid-stream, but the
    wire CAN swap (e.g. vendor stream drops and the app fills in). The
    user-visible attribute must reflect the most recent observation.
    """
    telemetry_coordinator.apply_frame(_voltage_frame(provider="RIVIAN_STREAM"))
    telemetry_coordinator.apply_frame(_voltage_frame(provider="APP_LOCATION"))

    assert _last_provider(telemetry_coordinator)[MOCK_VEHICLE_ID]["voltage"] == (
        "APP_LOCATION"
    )


# --- T3 + T4 + T5 (parametrised — sticky-on-omission across malformed shapes)


@pytest.mark.parametrize(
    "bad_provider",
    [
        pytest.param(_NO_PROVIDER_KEY, id="provider_key_absent"),
        pytest.param(None, id="provider_none"),
        pytest.param(123, id="provider_int"),
        pytest.param(True, id="provider_bool"),
        pytest.param([], id="provider_list"),
        pytest.param({}, id="provider_dict"),
        pytest.param("", id="provider_empty_string"),
        # Whitespace shapes — REJECT-ONLY under the symmetric-reject
        # contract: whitespace-only is malformed input;
        # leading/trailing on a valid token is also rejected (treat as
        # non-canonical wire shape rather than silently strip-and-keep).
        # Mirrors at all three boundaries (wire + sensor restore +
        # tracker restore) — single contract via
        # :func:`_is_clean_provider_str`.
        pytest.param("   ", id="whitespace_only_spaces"),
        pytest.param("\t\n", id="whitespace_only_tabs_newlines"),
        pytest.param("  RIVIAN_STREAM  ", id="leading_trailing_whitespace"),
    ],
)
async def test_apply_frame_provider_sticky_on_malformed_or_absent(
    telemetry_coordinator: AbrpTelemetryCoordinator,
    bad_provider: object,
) -> None:
    """Malformed / absent provider on a subsequent frame retains the prior value.

    Atomic sticky-on-omission contract — covers absent / non-string /
    empty-string. The symmetric-reject contract collapses what was
    originally split into
    two cases (live: ``""`` passes through / restore: ``""`` rejected)
    into one: ``""`` is malformed input at the wire boundary, treated
    the same as any other non-string. Per-stamp guard in
    ``_extract_provider``: ``isinstance(provider, str) and provider`` —
    rejects every shape above.

    Per  the
    "provider key absent from the block" case uses a module-level
    sentinel to disambiguate from "provider key present with value
    ``None``"; both shapes must round-trip to sticky.

    Per  the test
    body establishes the prior provider FIRST (so the test object isn't
    "starts empty, stays empty"), THEN injects the malformed frame and
    asserts the prior survives.
    """
    # Negation: establish prior provider so "stays empty" doesn't pass
    # vacuously.
    telemetry_coordinator.apply_frame(_voltage_frame(provider="RIVIAN_STREAM"))
    assert _last_provider(telemetry_coordinator)[MOCK_VEHICLE_ID]["voltage"] == (
        "RIVIAN_STREAM"
    )

    # Trigger: a frame with valid voltage but malformed/absent provider
    # — value_fn returns non-None (voltage IS present) so the stamp loop
    # iterates; the provider sub-check rejects, leaving the prior intact.
    telemetry_coordinator.apply_frame(
        _voltage_frame(volts=420.0, provider=bad_provider)
    )

    assert _last_provider(telemetry_coordinator)[MOCK_VEHICLE_ID]["voltage"] == (
        "RIVIAN_STREAM"
    )


# --- T6 -------------------------------------------------------------------


async def test_apply_frame_provider_per_metric_independent(
    telemetry_coordinator: AbrpTelemetryCoordinator,
) -> None:
    """Different metrics on the same frame get their own provider stamps.

    The probe finding: a Tesla vehicle commonly reports GPS from
    ``APP_LOCATION`` while battery telemetry flows from
    ``TESLA_FLEET_STREAM``. The coordinator's ``last_provider[vid]``
    must reflect both independently — not collapse to a single
    last-seen value.
    """
    frame = {
        "vehicleId": MOCK_VEHICLE_ID,
        "soc": {"frac": 0.85, "provider": "TESLA_FLEET_STREAM"},
        "location": {
            "lat": 37.7749,
            "long": -122.4194,
            "provider": "APP_LOCATION",
        },
    }

    telemetry_coordinator.apply_frame(frame)

    by_key = _last_provider(telemetry_coordinator)[MOCK_VEHICLE_ID]
    assert by_key["soc"] == "TESLA_FLEET_STREAM"
    assert by_key["location"] == "APP_LOCATION"


# --- T7 -------------------------------------------------------------------


async def test_apply_frame_provider_not_stamped_when_value_fn_returns_none(
    telemetry_coordinator: AbrpTelemetryCoordinator,
) -> None:
    """Bridging frame that omits the metric does NOT stamp provider for that key.

    Mirrors the per-frame stamp invariant for ``last_reported_at``: the
    stamp loop reads the UNMERGED frame's ``value_fn`` — frames that omit
    a metric must not refresh that metric's provider, even if a previous
    frame established one. Stamping from the merged state would defeat
    the user-visible "where is the most recent reading actually from?"
    contract.
    """
    # Frame 1 — voltage frame with provider stamps it.
    telemetry_coordinator.apply_frame(_voltage_frame(provider="RIVIAN_STREAM"))
    assert _last_provider(telemetry_coordinator)[MOCK_VEHICLE_ID]["voltage"] == (
        "RIVIAN_STREAM"
    )

    # Frame 2 — soc-only frame. value_fn for voltage returns None on this
    # unmerged frame, so the voltage row in last_provider is NOT touched.
    # A regression that stamped against the merged-state would either:
    #   (a) overwrite voltage's provider with the soc frame's provider, or
    #   (b) re-stamp voltage's provider to itself (harmless but masks the
    #       merged-state bug under a less obvious symptom).
    soc_frame = {
        "vehicleId": MOCK_VEHICLE_ID,
        "soc": {"frac": 0.5, "provider": "APP_LOCATION"},
    }
    telemetry_coordinator.apply_frame(soc_frame)

    by_key = _last_provider(telemetry_coordinator)[MOCK_VEHICLE_ID]
    assert by_key["voltage"] == "RIVIAN_STREAM"
    assert by_key["soc"] == "APP_LOCATION"


# --- T8 -------------------------------------------------------------------


async def test_apply_frame_provider_isolated_per_vehicle(
    telemetry_coordinator: AbrpTelemetryCoordinator,
) -> None:
    """Two vehicles' provider stamps never bleed across the ``last_provider`` map.

    Per  the seen / stamped
    state is keyed by ``(vehicle_id, metric_key)``; ``last_provider`` is
    a 2D ``dict[int, dict[str, str]]``. Multi-vehicle isolation is the
    minimum-bar contract; a regression that flattened the outer key
    would surface here as "vehicle 2's provider clobbers vehicle 1's".
    """
    telemetry_coordinator.apply_frame(_voltage_frame(provider="RIVIAN_STREAM"))
    telemetry_coordinator.apply_frame(
        _voltage_frame(vehicle_id=2, volts=380.0, provider="TESLA_FLEET_STREAM")
    )

    by_vehicle = _last_provider(telemetry_coordinator)
    assert by_vehicle[MOCK_VEHICLE_ID]["voltage"] == "RIVIAN_STREAM"
    assert by_vehicle[2]["voltage"] == "TESLA_FLEET_STREAM"


# ---------------------------------------------------------------------------
# forget_vehicle clears all four vehicle-keyed surfaces
# ---------------------------------------------------------------------------


async def test_forget_vehicle_clears_all_per_vehicle_surfaces(
    telemetry_coordinator: AbrpTelemetryCoordinator,
) -> None:
    """``coordinator.forget_vehicle(vid)`` clears every per-vehicle stamp / cache.

    drive frames
    for vehicles 1 + 2 so all four per-vehicle surfaces are populated
    for BOTH; trigger ``forget_vehicle(2)``; assert vehicle 2 is cleared
    on every surface AND vehicle 1 is retained unchanged.

    The four surfaces:

    1. ``data[vid]`` — merged telemetry snapshot.
    2. ``last_reported_at[vid]`` — per-metric wall-clock map.
    3. ``last_provider[vid]`` — per-metric provider map.
    4. ``_presence_seen`` — ``(vid, metric_key)`` set; clear every entry
       whose first element equals ``vid``.

    ``forget_vehicle`` is resolved via ``getattr`` with a no-op default
    so the test file imports cleanly even if the symbol is later
    renamed; an assertion that vehicle 2's surfaces are EMPTY
    post-trigger then fails loudly if the production helper drifts.

    Rationale: surfaces would otherwise grow per-vehicle in perpetuity
    (`last_provider` / `last_reported_at` rows accumulate for
    deselected or upstream-removed vehicles until config-entry reload).
    Hygiene, not a leak emergency — but stale-devices already knows
    when to remove a vehicle, so wiring a cleanup callback at that
    site keeps internal state honest with the registry.
    """
    # Drive a frame each for vehicle 1 + 2 so all four surfaces have
    # entries for BOTH.
    telemetry_coordinator.apply_frame(
        _voltage_frame(vehicle_id=MOCK_VEHICLE_ID, provider="RIVIAN_STREAM")
    )
    telemetry_coordinator.apply_frame(
        _voltage_frame(vehicle_id=2, volts=380.0, provider="TESLA_FLEET_STREAM")
    )
    # Force a presence_seen entry for both vehicles by registering a
    # predicate + applying frames. The stamp loop is independent, but
    # _presence_seen is populated via mark_metric_seen which runs from
    # the platform setup path; manually mark here.
    telemetry_coordinator.mark_metric_seen(MOCK_VEHICLE_ID, "voltage")
    telemetry_coordinator.mark_metric_seen(2, "voltage")

    # Negation pre-check: both vehicles populated on all four surfaces.
    assert MOCK_VEHICLE_ID in telemetry_coordinator.data
    assert 2 in telemetry_coordinator.data
    assert MOCK_VEHICLE_ID in _last_provider(telemetry_coordinator)
    assert 2 in _last_provider(telemetry_coordinator)
    assert MOCK_VEHICLE_ID in telemetry_coordinator.last_reported_at
    assert 2 in telemetry_coordinator.last_reported_at
    assert (MOCK_VEHICLE_ID, "voltage") in telemetry_coordinator._presence_seen
    assert (2, "voltage") in telemetry_coordinator._presence_seen

    # ``forget_vehicle`` is resolved via ``getattr`` (no-op default) so the
    # test imports cleanly even if the method is renamed; ``forget_vehicle(2)``
    # clears every per-vehicle surface for vid=2.
    forget = getattr(telemetry_coordinator, "forget_vehicle", lambda _vid: None)
    forget(2)

    # Vehicle 2 cleared on every surface.
    assert 2 not in telemetry_coordinator.data
    assert 2 not in _last_provider(telemetry_coordinator)
    assert 2 not in telemetry_coordinator.last_reported_at
    assert (2, "voltage") not in telemetry_coordinator._presence_seen

    # Vehicle 1 retained on every surface.
    assert MOCK_VEHICLE_ID in telemetry_coordinator.data
    assert _last_provider(telemetry_coordinator)[MOCK_VEHICLE_ID]["voltage"] == (
        "RIVIAN_STREAM"
    )
    assert "voltage" in telemetry_coordinator.last_reported_at[MOCK_VEHICLE_ID]
    assert (MOCK_VEHICLE_ID, "voltage") in telemetry_coordinator._presence_seen


async def test_forget_vehicle_tolerates_unknown_vehicle_id(
    telemetry_coordinator: AbrpTelemetryCoordinator,
) -> None:
    """Calling ``forget_vehicle`` for a never-seen vehicle is a no-op (no KeyError).

    Defensive guard: the cleanup callback fires from stale-devices
    removal; the listener
    might invoke ``forget_vehicle(vid)`` for a vehicle that never
    surfaced a telemetry frame (e.g. removed before its first SSE
    event). ``dict.pop(key, None)`` semantic — silent on absence.

    ``forget_vehicle`` MUST tolerate absence; a naïve ``del self.data[vid]``
    would KeyError here.
    """
    # No frames driven — coordinator empty.
    forget = getattr(telemetry_coordinator, "forget_vehicle", lambda _vid: None)
    forget(9999)

    assert telemetry_coordinator.data == {}
    assert _last_provider(telemetry_coordinator) == {}
    assert telemetry_coordinator.last_reported_at == {}
