"""Tests for GPS device_tracker restoration across HA restart.

Mirrors the sensor-side ``test_restore.py`` trajectories so a future
reader can map cross-platform restore behaviour line-by-line. The
tracker analogue diverges only where the platform contract differs
(coords live in ``state.attributes``, not ``state.state``;
``async_get_last_state()`` not ``async_get_last_sensor_data()``).

Trajectory matrix:

- Cold install (no registry, no cache): lazy contract preserved.
  Negation-then-trigger oracle.
- Restart with prior tracker registry entry → eager-create at setup
  BEFORE any frame.
- Restore + optional live-frame interaction (parametrized): coords
  persist, live frame overwrites, frame missing the location field
  preserves restored coords.
- Atomic-pair malformed-coords. Parametrized over 7 shapes
  (null/bool/non-number on each side + null_both). EITHER side
  failing the type guard collapses BOTH to None — half-coords
  nonsensical.
- Malformed restored ``last_reported_at`` ("banana") → attribute
  OMITTED entirely (not present-with-None).
- Vehicle deselected (stale-devices interaction): registry has entry
  but config_entry no longer selects vehicle → eager-create branch's
  ``selected_ids`` filter rejects, tracker not created.
- Composition pin: both ``latitude`` AND ``last_reported_at`` survive
  the persist→restore→re-persist round trip; framework-injected
  lat/long composes with our extra attribute.
- Per-frame stamp invariant: stamp refreshes only on frames whose
  ``_extract_lat_long`` returns non-None.

Uses plain ``mock_restore_cache`` (not the ``_with_extra_data``
variant) because TrackerEntity restoration reads ``state.attributes``
only; no ``SensorExtraStoredData`` payload to hydrate.

Atomic-pair parametrize is symmetric — bool_lng + non_number_lng
cases included alongside lat-side cases. The impl's restoration
boundary checks both fields with the same isinstance + bool-exclusion
guard.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun import freeze_time
import pytest

from homeassistant.components.abetterrouteplanner import AbrpData
from homeassistant.components.abetterrouteplanner.const import CONF_VEHICLE_IDS, DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import MOCK_VEHICLE_ID, SENSOR_TEST_SUB, build_telemetry_frame

from tests.common import MockConfigEntry, mock_restore_cache

LOCATION_ENTITY_ID = "device_tracker.rivian_r2_2027_standard_long_range_location"
LOCATION_UNIQUE_ID = f"{SENSOR_TEST_SUB}_{MOCK_VEHICLE_ID}_location"

# Provider sentinel for "this restore-state should omit the ``provider``
# attribute entirely" — distinct from passing the literal ``None`` value.
_PROVIDER_UNSET: Any = object()

RESTORED_PROVIDER = "APP_LOCATION"

# Restored slot anchors. Sample SF coords chosen so failure traces stay
# visually distinct from any test-bench lat/long noise.
RESTORED_LAT = 37.7749
RESTORED_LNG = -122.4194
RESTORED_STAMP_ISO = "2026-05-20T12:00:00+00:00"
RESTORED_STAMP_DT = datetime(2026, 5, 20, 12, 0, 0, tzinfo=UTC)


def _push_frame(entry: MockConfigEntry, frame: dict[str, Any]) -> None:
    """Inject a synthesized telemetry frame through the coordinator boundary."""
    runtime: AbrpData = entry.runtime_data
    runtime.telemetry_coordinator.apply_frame(frame)


def _location_frame(vehicle_id: int, *, lat: float, lng: float) -> dict[str, Any]:
    """Build a wire-shape frame containing a single ``location`` block.

    Mirrors ``test_device_tracker._location_frame``. Defined locally rather
    than imported because the restore test file should stand alone and the
    helper is a one-liner. Wire keys per ``[[reference_abrp_telemetry_wire
    _key_naming]]``: outer is ``location``, inner is ``lat`` / ``long``.
    """
    return {
        "vehicleId": vehicle_id,
        "location": {"lat": lat, "long": lng},
    }


def _tracker_restored_state(
    *,
    lat: Any = RESTORED_LAT,
    lng: Any = RESTORED_LNG,
    last_reported_at: str | None = RESTORED_STAMP_ISO,
    provider: Any = _PROVIDER_UNSET,
) -> State:
    """Build a ``State`` for ``mock_restore_cache`` representing the prior session.

    Both ``lat`` and ``lng`` are typed ``Any`` so the malformed-coords
    parametrize can pass bool/non-numeric values into the cache and exercise
    the impl's isinstance + bool-exclusion guard. The cache helper
    JSON-round-trips ``attributes`` (mirroring the recorder), so passing a
    bool here flows through as ``True``/``False`` → the integration sees
    the same bool the recorder would surface in a real schema-drift
    scenario.

    ``state.state`` carries ``"not_home"`` as an opaque placeholder; HA's
    zone detector recomputes the real zone label from the restored coords
    after the entity is added, so the placeholder doesn't affect test
    outcomes. The tests assert on ``entity.latitude`` / ``.longitude`` /
    ``state.attributes["last_reported_at"]``, never on ``state.state``.
    """
    attributes: dict[str, Any] = {"latitude": lat, "longitude": lng}
    if last_reported_at is not None:
        attributes["last_reported_at"] = last_reported_at
    if provider is not _PROVIDER_UNSET:
        attributes["provider"] = provider
    return State(LOCATION_ENTITY_ID, "not_home", attributes=attributes)


async def _restart_setup(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    *,
    entity_registry: er.EntityRegistry | None = None,
    preseed_location: bool = False,
    restored_states: list[State] | None = None,
) -> None:
    """Set up the integration simulating an HA restart for the device_tracker domain.

    Mirrors ``test_restore._restart_setup`` shape but targeting the
    device_tracker domain on the registry pre-seed and using the
    state-only ``mock_restore_cache`` (TrackerEntity restoration
    reads ``state.attributes`` only).

    The ``suggested_object_id`` matches the slug the integration would itself
    compute (``has_entity_name=True`` + device name + translation_key
    ``"location"``) — without it the auto-slug ``f"device_tracker_
    {platform}_{unique_id}"`` would mismatch the cache lookup and the
    restoration would silently miss.
    """
    hass.set_state(CoreState.not_running)
    if restored_states is not None:
        mock_restore_cache(hass, restored_states)
    assert await async_setup_component(hass, "auth", {})
    assert await async_setup_component(hass, DOMAIN, {})
    entry.add_to_hass(hass)
    if preseed_location and entity_registry is not None:
        entity_registry.async_get_or_create(
            domain="device_tracker",
            platform=DOMAIN,
            unique_id=LOCATION_UNIQUE_ID,
            config_entry=entry,
            suggested_object_id="rivian_r2_2027_standard_long_range_location",
        )
    with patch(
        "homeassistant.components.abetterrouteplanner.PREWARM_WINDOW_SECONDS",
        0,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()


# ---------------------------------------------------------------------------
# T1 — Cold install (no prior registry, no restore cache)
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_cold_install_lazy_create_preserved(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_seed_responses: AsyncMock,
) -> None:
    """Cold install: no registry, no seed, no SSE → no tracker; trigger creates.

    Negation-then-trigger oracle: pins that the eager-from-registry
    branch does NOT bleed onto fresh installs; the first non-None
    location frame still triggers lazy creation through the existing
    dispatcher.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _restart_setup(hass, config_entry_with_vehicles)

    # Negation: no prior registry → no eager-create at setup.
    assert hass.states.get(LOCATION_ENTITY_ID) is None

    # Trigger: first location frame fires the dispatcher → tracker created.
    _push_frame(
        config_entry_with_vehicles,
        _location_frame(MOCK_VEHICLE_ID, lat=37.7749, lng=-122.4194),
    )
    await hass.async_block_till_done()

    state = hass.states.get(LOCATION_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("latitude") == 37.7749
    assert state.attributes.get("longitude") == -122.4194


# ---------------------------------------------------------------------------
# T2 — Restart with prior tracker registry → eager-create from registry
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_restart_eager_create_from_registry(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """Prior tracker registry entry → eager-created BEFORE any frame.

    Same UX bug class as wake-only sensors (16h Unavailable on parked
    vehicles) but more user-visible: geofence automations need the
    tracker entity to EXIST immediately on restart, not after the next
    wake event. The eager-create branch must instantiate the tracker
    even when no live or seed frame carries ``location`` yet.

    No restore cache is wired here — the tracker exists but its
    ``latitude`` / ``longitude`` are None until the next frame
    (acceptable degradation; matches the sensor restore pattern).
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_location=True,
    )

    # State object exists (eager-created); coords may be None until a
    # frame or restore cache lands. Contract: state-exists, not
    # state-has-coords.
    state = hass.states.get(LOCATION_ENTITY_ID)
    assert state is not None


# ---------------------------------------------------------------------------
# T3 + T4 + T5 — Restore + optional live-frame interaction (parametrized)
# ---------------------------------------------------------------------------


# Named push-frame helpers used by the parametrized restore + optional-frame
# matrix below. Encoding each trajectory's "what frame to push" as a
# Callable keeps the test body branch-free per CLAUDE.md; the prior shape
# carried two nested ``if``s (frame-present? + lat-key?) that disguised the
# trajectory dispatch as ad-hoc dict probing.


def _no_op_push(entry: MockConfigEntry) -> None:
    """Push no frame — the ``restored_only_before_first_frame`` trajectory."""


def _push_location_nyc(entry: MockConfigEntry) -> None:
    """Push a live location frame for NYC — the ``live_frame_overwrites_restored`` trajectory."""
    _push_frame(entry, _location_frame(MOCK_VEHICLE_ID, lat=40.7128, lng=-74.0060))


def _push_bridging_soc(entry: MockConfigEntry) -> None:
    """Push a bridging frame with soc only — preserves restored coords."""
    _push_frame(entry, build_telemetry_frame(MOCK_VEHICLE_ID, soc=0.5))


@pytest.mark.parametrize(
    ("push_frame", "expected_lat", "expected_lng"),
    [
        pytest.param(
            _no_op_push,
            RESTORED_LAT,
            RESTORED_LNG,
            id="restored_only_before_first_frame",
        ),
        pytest.param(
            _push_location_nyc,
            40.7128,
            -74.0060,
            id="live_frame_overwrites_restored",
        ),
        pytest.param(
            _push_bridging_soc,
            RESTORED_LAT,
            RESTORED_LNG,
            id="bridging_frame_missing_location_preserves_restored",
        ),
    ],
)
@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_restore_coords_then_optional_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
    push_frame: Callable[[MockConfigEntry], None],
    expected_lat: float,
    expected_lng: float,
) -> None:
    """Restored coords persist; live frame overrides only when it carries location.

    Covers three restore trajectories in one parametrize because they
    share the restore-setup → optional-frame → assert-coords structure.
    Each id exercises a distinct path:

    - ``restored_only_before_first_frame`` — T3. Live ``_coords()``
      returns None; property fallback surfaces ``_restored_coords``.
    - ``live_frame_overwrites_restored`` — T4. Live ``_coords()``
      returns NYC; property prefers live over restored.
    - ``bridging_frame_missing_location_preserves_restored`` — T5.
      Frame carries soc but no location; merge-preserved-state's
      ``_coords()`` returns None (per
       the merge keeps prior
      location, but the value_fn evaluates the unmerged frame for the
      stamp loop, not the merged state for ``_coords``); fallback to
      restored.

    The ``push_frame`` callable column encodes the trajectory-specific
    dispatch in the parametrize table, keeping the test body branch-free.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_location=True,
        restored_states=[_tracker_restored_state()],
    )

    push_frame(config_entry_with_vehicles)
    await hass.async_block_till_done()

    state = hass.states.get(LOCATION_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("latitude") == expected_lat
    assert state.attributes.get("longitude") == expected_lng


# ---------------------------------------------------------------------------
# T6 — Atomic-pair malformed coords: EITHER side bad → BOTH collapse
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("bad_lat", "bad_lng"),
    [
        pytest.param(None, RESTORED_LNG, id="null_lat"),
        pytest.param(RESTORED_LAT, None, id="null_lng"),
        pytest.param("banana", RESTORED_LNG, id="non_number_lat"),
        pytest.param(RESTORED_LAT, "banana", id="non_number_lng"),
        pytest.param(True, RESTORED_LNG, id="bool_lat"),
        pytest.param(RESTORED_LAT, False, id="bool_lng"),
        pytest.param(None, None, id="null_both"),
    ],
)
@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_atomic_pair_malformed_coords_omits_restoration(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
    bad_lat: Any,
    bad_lng: Any,
) -> None:
    """If EITHER lat or lng fails the type guard, BOTH ``_restored_coords`` collapses.

    A half-restored position is nonsensical (lat without lng has no
    geographic meaning; bool sneaks
    past ``isinstance(_, int)`` because ``bool ⊂ int``). The impl's
    restoration boundary mirrors ``_extract_lat_long``'s isinstance +
    bool-exclusion guard — if either field fails, BOTH stay None.

    Parametrize
    + sibling-symmetry: every bad-shape x every side
    (4 lat-side + 4 lng-side - 1 dedup since ``null_both`` is shared = 7
    cases). Pins atomic-pair semantic from both directions; a regression
    that drops only one side's guard surfaces as a partial-restore on the
    other side's parametrize id, not a silent everywhere-fail.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_location=True,
        restored_states=[_tracker_restored_state(lat=bad_lat, lng=bad_lng)],
    )

    state = hass.states.get(LOCATION_ENTITY_ID)
    assert state is not None
    # Atomic-pair: BOTH attributes must be None (no half-restore).
    assert state.attributes.get("latitude") is None
    assert state.attributes.get("longitude") is None


# ---------------------------------------------------------------------------
# T7 — Malformed restored last_reported_at: attribute omitted entirely
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_malformed_restored_stamp_omits_attribute(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """Malformed restored stamp → ``last_reported_at`` ABSENT from attributes.

    Mirrors §6.E for the tracker domain. ``datetime.fromisoformat
    ("banana")`` raises ``ValueError``; the impl's
    ``contextlib.suppress(ValueError)`` leaves ``_restored_last_reported
    _at`` at None and ``extra_state_attributes`` omits the key entirely.
    Omit beats both expose-as-is ("banana" in templates) and ``None``
    (renders as "null").

    The coords still restore: the malformed stamp affects only the stamp
    slot, not the coord slot. This distinguishes "omit the bad field"
    from "lose all restoration".
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_location=True,
        restored_states=[_tracker_restored_state(last_reported_at="banana")],
    )

    state = hass.states.get(LOCATION_ENTITY_ID)
    assert state is not None
    # Coords still restore — the malformed stamp doesn't poison the pair.
    assert state.attributes.get("latitude") == RESTORED_LAT
    assert state.attributes.get("longitude") == RESTORED_LNG
    # Stamp slot: attribute key must be ABSENT, not present-with-None.
    assert "last_reported_at" not in state.attributes


# ---------------------------------------------------------------------------
# §6.E composition pin — both lat AND last_reported_at compose correctly
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_restore_composition_lat_lng_and_last_reported_at(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """Framework-injected lat/long composes with custom ``last_reported_at``.

    ``TrackerEntity`` auto-injects ``latitude``
    + ``longitude`` into ``state.attributes`` from the entity properties;
    the new ``extra_state_attributes`` contributes ``last_reported_at``.
    They compose (HA merges), and ALL THREE must appear in the persisted
    state.

    Pins datetime round-trip : / §6.H: recorder serialises
    ``datetime → isoformat()`` via HA's ``JSONEncoder``; the restore
    path parses back to ``datetime`` via ``datetime.fromisoformat``.
    Assert both type (``isinstance(..., datetime)``) and value.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_location=True,
        restored_states=[_tracker_restored_state()],
    )

    state = hass.states.get(LOCATION_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("latitude") == RESTORED_LAT
    assert state.attributes.get("longitude") == RESTORED_LNG
    stamp = state.attributes.get("last_reported_at")
    assert isinstance(stamp, datetime)
    assert stamp == RESTORED_STAMP_DT


# ---------------------------------------------------------------------------
# T8 — Vehicle deselected mid-restore (stale-devices interaction)
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_deselected_vehicle_skips_eager_create(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """Registry has tracker entry but vehicle no longer in CONF_VEHICLE_IDS → skip.

    User reconfigured between sessions
    to remove the vehicle: the entity_registry still has the row (until
    stale-devices cleanup fires on the next garage poll), but the
    config_entry's ``CONF_VEHICLE_IDS`` no longer lists this vehicle. The
    eager-create branch's ``selected_ids`` filter must reject; the
    tracker must NOT spuriously surface for an unselected vehicle.

    Composes with  — the actual cleanup
    happens via the garage coordinator's stale-devices listener, but
    the safety net is the eager-create filter.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}
    # Entry exists but CONF_VEHICLE_IDS is empty (user just deselected this vehicle).
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SENSOR_TEST_SUB,
        data={
            "auth_implementation": DOMAIN,
            "token": token_entry,
            CONF_VEHICLE_IDS: [],
        },
    )

    await _restart_setup(
        hass,
        entry,
        entity_registry=entity_registry,
        preseed_location=True,
        restored_states=[_tracker_restored_state()],
    )

    # Eager-create branch must NOT add the tracker even though the
    # registry row + restore cache both exist — the vehicle is no longer
    # selected and the filter rejects.
    assert hass.states.get(LOCATION_ENTITY_ID) is None


# ---------------------------------------------------------------------------
# Per-frame stamp invariant (mirrors for the location key)
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_last_reported_at_stamps_per_location_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """Stamp refreshes only on frames whose ``_extract_lat_long`` returns non-None.

    Mirrors's ``test_last_reported_at_stamps_per_frame_not_per_merged
    _state`` for the tracker domain. The coordinator merge preserves the
    prior location across bridging frames (per
    ); the stamp must NOT
    refresh on those bridging frames or the user reads "GPS reported
    2 minutes ago" when the vehicle's actually been silent for hours.

    Three frames at distinct timestamps:

    1. t1 — frame with location → stamp = t1.
    2. t2 — frame with soc only (no location) → stamp STILL t1.
    3. t3 — frame with location → stamp = t3.

    The impl extends the stamp loop to iterate the
    concatenation ``(*SENSOR_VALUE_FNS, LOCATION_VALUE_FN)`` — module-
    level constants both, so the pre-warm window is preserved.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_location=True,
    )

    t1 = datetime(2026, 5, 24, 10, 0, 0, tzinfo=UTC)
    t2 = datetime(2026, 5, 24, 10, 5, 0, tzinfo=UTC)
    t3 = datetime(2026, 5, 24, 10, 10, 0, tzinfo=UTC)

    with freeze_time(t1):
        _push_frame(
            config_entry_with_vehicles,
            _location_frame(MOCK_VEHICLE_ID, lat=37.7749, lng=-122.4194),
        )
        await hass.async_block_till_done()

    state = hass.states.get(LOCATION_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("last_reported_at") == t1

    with freeze_time(t2):
        # Frame WITHOUT location — merge preserves prior coords in the
        # merged state, but the stamp must not refresh because THIS
        # frame's _extract_lat_long returns None on a frame without
        # the ``location`` key.
        _push_frame(
            config_entry_with_vehicles,
            build_telemetry_frame(MOCK_VEHICLE_ID, soc=0.5),
        )
        await hass.async_block_till_done()

    state = hass.states.get(LOCATION_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("last_reported_at") == t1

    with freeze_time(t3):
        _push_frame(
            config_entry_with_vehicles,
            _location_frame(MOCK_VEHICLE_ID, lat=40.7128, lng=-74.0060),
        )
        await hass.async_block_till_done()

    state = hass.states.get(LOCATION_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("last_reported_at") == t3


# ---------------------------------------------------------------------------
# Provider attribute on the GPS device_tracker
# ---------------------------------------------------------------------------
#
# Tracker mirror of the sensor-side contract: provider lives in
# ``extra_state_attributes``, composes per-attribute with the existing
# ``last_reported_at``, and rejects ``""``/non-string shapes on BOTH live
# and restore paths (symmetric reject).


def _location_frame_with_provider(
    *,
    lat: float = 37.7749,
    lng: float = -122.4194,
    provider: str | None = None,
) -> dict[str, Any]:
    """Construct a location telemetry frame; optionally embed ``provider``.

    Local helper rather than mutating ``_location_frame`` at the top of
    this file (the existing helper is shared with the GPS-restore
    parametrize tables and has a stable signature). Provider lives
    inside the ``location`` block per ``WithTimeAndProvider``.
    """
    block: dict[str, Any] = {"lat": lat, "long": lng}
    if provider is not None:
        block["provider"] = provider
    return {"vehicleId": MOCK_VEHICLE_ID, "location": block}


# --- GS1 ------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_tracker_provider_attribute_appears_from_live_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_seed_responses: AsyncMock,
) -> None:
    """A live location frame with ``provider`` surfaces it on the tracker.

    Cold install path — the lazy-create dispatcher fires on the first
    non-None location frame and the tracker immediately exposes the
    provider string alongside lat/long.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _restart_setup(hass, config_entry_with_vehicles)

    _push_frame(
        config_entry_with_vehicles,
        _location_frame_with_provider(provider=RESTORED_PROVIDER),
    )
    await hass.async_block_till_done()

    state = hass.states.get(LOCATION_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("provider") == RESTORED_PROVIDER


# --- GS2 ------------------------------------------------------------------


@pytest.mark.parametrize(
    "live_provider",
    [
        pytest.param(None, id="frame_omits_provider"),
        pytest.param("", id="frame_empty_string_provider"),
    ],
)
@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_tracker_provider_attribute_absent_when_live_frame_lacks_provider(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_seed_responses: AsyncMock,
    live_provider: str | None,
) -> None:
    """No prior + frame without usable provider → ``provider`` key absent on tracker.

    Symmetric reject — empty-string and absent-key collapse to the
    same observable outcome. The assertion is on attribute ABSENCE,
    not present-with-null. ``latitude`` /
    ``longitude`` survive as the trigger pin so a regression that
    blanked the whole attributes dict fails the second assertion too.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _restart_setup(hass, config_entry_with_vehicles)

    _push_frame(
        config_entry_with_vehicles,
        _location_frame_with_provider(provider=live_provider),
    )
    await hass.async_block_till_done()

    state = hass.states.get(LOCATION_ENTITY_ID)
    assert state is not None
    assert "provider" not in state.attributes
    # Lat/long still surface — the malformed provider doesn't poison
    # the rest of the attributes dict.
    assert state.attributes.get("latitude") == 37.7749
    assert state.attributes.get("longitude") == -122.4194


# --- GS3 ------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_tracker_provider_attribute_restored_from_recorder(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """Restored tracker ``provider`` surfaces alongside lat/long + last_reported_at.

    Three-attribute composition: provider + last_reported_at (custom
    extras) + framework-injected lat/long. All three survive the
    persist→restore→re-publish round trip.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_location=True,
        restored_states=[_tracker_restored_state(provider=RESTORED_PROVIDER)],
    )

    state = hass.states.get(LOCATION_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("provider") == RESTORED_PROVIDER
    assert state.attributes.get("latitude") == RESTORED_LAT
    assert state.attributes.get("longitude") == RESTORED_LNG
    stamp = state.attributes.get("last_reported_at")
    assert isinstance(stamp, datetime)
    assert stamp == RESTORED_STAMP_DT


# --- GS4 ------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_tracker_provider_per_attribute_live_wins_over_restored(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """Per-attribute composition on the tracker: live last_reported_at + restored provider.

    Mirrors the sensor S4 contract for the tracker. A live frame with
    location but no provider keeps the restored provider while the
    ``last_reported_at`` axis flips to the live frozen time.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_location=True,
        restored_states=[_tracker_restored_state(provider=RESTORED_PROVIDER)],
    )

    t2 = datetime(2026, 5, 24, 14, 0, 0, tzinfo=UTC)
    with freeze_time(t2):
        _push_frame(
            config_entry_with_vehicles,
            _location_frame_with_provider(
                lat=40.7128,
                lng=-74.0060,
                provider=None,
            ),
        )
        await hass.async_block_till_done()

    state = hass.states.get(LOCATION_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("provider") == RESTORED_PROVIDER
    assert state.attributes.get("last_reported_at") == t2
    # value-axis pin. A regression that decoupled coordinate-
    # publish from attribute-publish would slip past the provider /
    # stamp assertions above. Pin the live lat/lng from the same frame.
    assert state.attributes.get("latitude") == 40.7128
    assert state.attributes.get("longitude") == -74.0060


# --- GS5 + GS6 (parametrised — symmetric malformed-restore rejection) ----


@pytest.mark.parametrize(
    "restored_provider",
    [
        pytest.param("", id="restored_empty_string"),
        pytest.param(123, id="restored_int"),
        pytest.param(True, id="restored_bool"),
        pytest.param({"nested": "dict"}, id="restored_dict"),
        pytest.param([1, 2, 3], id="restored_list"),
        pytest.param(None, id="restored_none"),
        # whitespace shapes — REJECT-ONLY. Tracker
        # mirror of the sensor restore-guard parametrize; single contract
        # with the wire boundary in ``_extract_provider``.
        pytest.param("   ", id="restored_whitespace_only_spaces"),
        pytest.param("\t\n", id="restored_whitespace_only_tabs_newlines"),
        pytest.param(
            "  APP_LOCATION  ",
            id="restored_leading_trailing_whitespace",
        ),
    ],
)
@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_tracker_provider_attribute_absent_when_restored_value_malformed(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
    restored_provider: Any,
) -> None:
    """Malformed restored ``provider`` → attribute OMITTED on the tracker.

    Symmetric reject  — every adversarial shape that the
    coordinator's ``_extract_provider`` would reject is also rejected on
    the restore path. Composition pin: lat/long + last_reported_at survive
    so a regression that blanked the whole attributes dict fails on those
    other axes.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_location=True,
        restored_states=[_tracker_restored_state(provider=restored_provider)],
    )

    state = hass.states.get(LOCATION_ENTITY_ID)
    assert state is not None
    assert "provider" not in state.attributes
    # Other axes survive — malformed provider doesn't collapse the
    # whole attribute dict.
    assert state.attributes.get("latitude") == RESTORED_LAT
    assert state.attributes.get("longitude") == RESTORED_LNG
    stamp = state.attributes.get("last_reported_at")
    assert isinstance(stamp, datetime)
    assert stamp == RESTORED_STAMP_DT


# ---------------------------------------------------------------------------
# int lat/lng restored → float coercion at the boundary
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_tracker_int_lat_lng_cast_to_float_on_restore(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """Restored ``int`` lat/lng must surface as ``float`` on the entity.

    Note: the wire spec is ``float``, but
    ``state.attributes`` round-trip through the recorder's JSONEncoder
    leaves an integer-shaped value as a Python ``int`` on restore. The
    isinstance guard ``isinstance(lat, (int, float)) and not
    isinstance(lat, bool)`` admits the int; today's restore code
    stores the bare value → ``state.attributes['latitude']`` reports
    ``42`` (int) instead of ``42.0`` (float).

    Single RED. Today's code path:
    ``self._restored_coords = (lat, lng)`` keeps the int as-is. After
    fix: ``self._restored_coords = (float(lat), float(lng))`` at the
    restore boundary; the type guarantee mirrors the live-path
    ``_extract_lat_long`` return shape.

    Latitude 42 / longitude -71 chosen so ``float(42) == 42`` succeeds
    on equality but ``isinstance(_, float)`` fails on the int-form —
    the regression is value-equal but type-wrong. A future template
    that does ``state.attributes.latitude | float`` would still work
    today, but a typed-consumer (e.g. ``isinstance(x, float)`` guard
    in some downstream automation) would silently misbehave.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_location=True,
        # Integer-valued lat/lng — Python ints, not floats. Mimics the
        # recorder round-tripping ``42.0`` as JSON ``42``.
        restored_states=[_tracker_restored_state(lat=42, lng=-71)],
    )

    state = hass.states.get(LOCATION_ENTITY_ID)
    assert state is not None
    lat = state.attributes.get("latitude")
    lng = state.attributes.get("longitude")
    # Value-equality pin so the regression is bound to the value too.
    assert lat == 42
    assert lng == -71
    # Type-equality pin: the coordinate values must be floats, not ints.
    assert isinstance(lat, float)
    assert isinstance(lng, float)


# ---------------------------------------------------------------------------
# tracker mirror: eager-create probe skips foreign-entry rows
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_tracker_foreign_config_entry_row_skipped_by_eager_probe(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    token_entry: dict[str, Any],
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """Tracker eager-create probe MUST filter on ``config_entry_id``.

    Tracker mirror of the sensor test. Same contract: a registry row
    owned by a foreign config_entry with a colliding ``unique_id``
    (same OIDC ``sub`` formula) must NOT be claimed by the
    entry-under-test.

    GREEN-on-arrival regression pin. HA core's entity_platform
    incidentally blocks today via duplicate-entity-id rejection during
    the under-test entry's eager ``async_add_entities`` call. The
    defensive integration-side filter makes the same outcome
    deterministic at the integration boundary — insulating from a
    future HA core change that admits the rebind.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    foreign_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SENSOR_TEST_SUB,
        entry_id="01FOREIGNTRACKERENTRYIDXXXX",
        data={
            "auth_implementation": DOMAIN,
            "token": token_entry,
            CONF_VEHICLE_IDS: [str(MOCK_VEHICLE_ID)],
        },
    )
    foreign_entry.add_to_hass(hass)
    foreign_row = entity_registry.async_get_or_create(
        domain="device_tracker",
        platform=DOMAIN,
        unique_id=LOCATION_UNIQUE_ID,
        config_entry=foreign_entry,
        suggested_object_id="rivian_r2_2027_standard_long_range_location",
    )

    await _restart_setup(hass, config_entry_with_vehicles)

    refetched = entity_registry.async_get(foreign_row.entity_id)
    assert refetched is not None
    assert refetched.config_entry_id == foreign_entry.entry_id
