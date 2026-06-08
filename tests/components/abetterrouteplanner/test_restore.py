"""Tests for sensor state restoration across HA restart.

Covers the recorder-backed restoration path:
``_sensor_value_fns.py`` extract → coord-side ``last_reported_at``
stamp → sensor-side ``RestoreSensor`` mixin + eager-from-registry.

Trajectory matrix:

- Cold install (no prior registry, no restore cache): lazy contract
  preserved — no eager-create bleed onto fresh installs.
- Restart with prior entity-registry entry: eager-create from the
  registry probe BEFORE the first SSE frame.
- Restore + optional live-frame interaction (parametrized):
  native_value persists across restart, live frame overwrites, frame
  missing the field preserves restored value, restore is observable
  before the first SSE frame.
- `extra_state_attributes["last_reported_at"]` round-trips recorder
  string → ``datetime``.
- Malformed restored stamp ("banana"): attribute omitted entirely
  (not present-with-None).
- `last_reported_at` stamps per-frame on non-None value_fn return, NOT
  per merged-state. Skip-stamp on frame missing the field even when
  the merged state retains the prior value.

Telemetry voltage is the representative wake-only sensor under test;
the contract is universal so per-sensor parametrize parity is implicit
(any tester pinning soc/power/odometer would write the same shape
against the same class).
"""

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

from tests.common import MockConfigEntry, mock_restore_cache_with_extra_data

VOLTAGE_ENTITY_ID = "sensor.rivian_r2_2027_standard_long_range_voltage"
VOLTAGE_UNIQUE_ID = f"{SENSOR_TEST_SUB}_{MOCK_VEHICLE_ID}_voltage"

# Provider sentinel for "this restore-state should omit the ``provider``
# attribute entirely" — distinct from passing the literal ``None`` value
# (which would land as a present-but-null attribute).
_PROVIDER_UNSET: Any = object()

RESTORED_PROVIDER = "RIVIAN_STREAM"

# Restored slot anchors. Times chosen so freeze_time ranges in T7 are
# visibly disjoint from this baseline in failure traces.
RESTORED_VOLTAGE = 410.0
RESTORED_STAMP_ISO = "2026-05-20T12:00:00+00:00"
RESTORED_STAMP_DT = datetime(2026, 5, 20, 12, 0, 0, tzinfo=UTC)


def _push_frame(entry: MockConfigEntry, frame: dict[str, Any]) -> None:
    """Inject a synthesized telemetry frame through the coordinator boundary."""
    runtime: AbrpData = entry.runtime_data
    runtime.telemetry_coordinator.apply_frame(frame)


def _voltage_restored_state(
    *,
    native_value: float | None = RESTORED_VOLTAGE,
    last_reported_at: str | None = RESTORED_STAMP_ISO,
    provider: Any = _PROVIDER_UNSET,
) -> tuple[State, dict[str, Any]]:
    """Build a (State, extra_data) tuple for ``mock_restore_cache_with_extra_data``.

    ``last_reported_at`` is supplied as an ISO string mirroring what the
    recorder serialises from a ``datetime`` via HA's ``JSONEncoder``
    (``helpers/json.py:28-29``). The restore path is
    expected to parse it back to a ``datetime`` via
    ``datetime.fromisoformat`` on the stored string; on parse failure
    the attribute is OMITTED, not surfaced as ``None``.

    ``provider`` defaults to the sentinel :data:`_PROVIDER_UNSET` which
    keeps the attribute absent from the State for callers that do not
    care about the provider slot. Passing any concrete value (string,
    int, None, empty string, etc.) lands it under the ``provider`` key
    in ``State.attributes`` so the integration's restore path exercises
    its type-guard branch.
    """
    attributes: dict[str, Any] = {}
    if last_reported_at is not None:
        attributes["last_reported_at"] = last_reported_at
    if provider is not _PROVIDER_UNSET:
        attributes["provider"] = provider
    state = State(
        VOLTAGE_ENTITY_ID,
        str(native_value) if native_value is not None else "unknown",
        attributes=attributes,
    )
    extra_data: dict[str, Any] = {
        "native_value": native_value,
        "native_unit_of_measurement": "V",
    }
    return state, extra_data


async def _restart_setup(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    *,
    entity_registry: er.EntityRegistry | None = None,
    preseed_registry_keys: list[str] | None = None,
    restored_states: list[tuple[State, dict[str, Any]]] | None = None,
) -> None:
    """Set up the integration simulating an HA restart with optional prior state.

    Sequence mirrors ``tests/components/here_travel_time/test_sensor.py``
    + :

    1. ``hass.set_state(CoreState.not_running)`` — required for
       ``RestoreEntity`` / ``RestoreSensor`` to surface its cache.
    2. ``mock_restore_cache_with_extra_data(...)`` — wire the recorder
       cache so ``async_get_last_sensor_data`` returns prior values.
    3. ``entry.add_to_hass`` + optional entity-registry pre-seeding so
       the eager-from-registry branch finds prior entries.
    4. Pre-warm window patched to ``0`` so setup completes without
       waiting on the real prewarm sleep — but ``asyncio.sleep`` is
       NOT module-patched (would short-circuit SSE backoff).
    5. ``EVENT_HOMEASSISTANT_STARTED`` fired at the end so any
       post-start hooks settle before assertions run.
    """
    hass.set_state(CoreState.not_running)
    if restored_states is not None:
        mock_restore_cache_with_extra_data(hass, restored_states)
    assert await async_setup_component(hass, "auth", {})
    assert await async_setup_component(hass, DOMAIN, {})
    entry.add_to_hass(hass)
    if preseed_registry_keys and entity_registry is not None:
        for key in preseed_registry_keys:
            # ``suggested_object_id`` so the pre-seeded entry's entity_id
            # matches the slug the integration would itself compute
            # (``has_entity_name=True`` + device name + translation_key) at
            # first registration in a prior session. Without it the auto-
            # slug falls back to ``f"{platform}_{unique_id}"`` and the
            # restore-cache State (keyed by entity_id) misses.
            entity_registry.async_get_or_create(
                domain="sensor",
                platform=DOMAIN,
                unique_id=f"{SENSOR_TEST_SUB}_{MOCK_VEHICLE_ID}_{key}",
                config_entry=entry,
                suggested_object_id=f"rivian_r2_2027_standard_long_range_{key}",
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
# T1 — Cold install (no prior registry, no restore cache): lazy preserved
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_cold_install_lazy_create_preserved(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_seed_responses: AsyncMock,
) -> None:
    """Cold install: no registry, no seed, no SSE → no entity yet; trigger creates.

    Negation-then-trigger oracle: pins that the eager-from-registry
    branch does NOT spuriously create entities at setup when no prior
    registry row exists. The first non-None voltage frame then triggers
    lazy creation via the dispatcher — the lazy-creation contract must
    survive across HA restart unbroken.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _restart_setup(hass, config_entry_with_vehicles)

    # Negation: no prior registry → no eager-create at setup.
    assert hass.states.get(VOLTAGE_ENTITY_ID) is None

    # Trigger: first voltage frame fires the dispatcher → entity created.
    _push_frame(
        config_entry_with_vehicles,
        build_telemetry_frame(MOCK_VEHICLE_ID, voltage=400.0),
    )
    await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.state == "400.0"


# ---------------------------------------------------------------------------
# T2 — Restart with prior registry → eager-create from registry probe
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_restart_eager_create_from_registry(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """Prior voltage registry entry → entity eager-created BEFORE any frame.

    Addresses the user-confirmed bug (16h Unavailable on parked
    vehicles). The setup-time registry probe
    must instantiate the entity even when no live or seed frame carries
    the field, so the user's UI shows a sensor row immediately on
    restart rather than after the next wake event.

    No restore cache is wired here — the entity exists but its
    ``native_value`` falls back to ``None`` until the next frame
    (acceptable degradation per §1.7 trajectory 3 in the plan;
    matches legacy behaviour for the "registry present but recorder
    pruned" path).
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_registry_keys=["voltage"],
    )

    # State object exists (eager-created); value may be unknown until
    # a frame or restore cache lands. Contract: state-exists, not
    # state-has-value.
    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None


# ---------------------------------------------------------------------------
# T3 + T4 + T5 + T8 — Restore + optional live-frame (parametrized)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("frame_after_setup", "expected_state"),
    [
        pytest.param(
            None, str(RESTORED_VOLTAGE), id="restored_only_before_first_frame"
        ),
        pytest.param(
            {"voltage": 420.0},
            "420.0",
            id="live_frame_overwrites_restored",
        ),
        pytest.param(
            {"soc": 0.5},
            str(RESTORED_VOLTAGE),
            id="live_frame_missing_field_preserves_restored",
        ),
    ],
)
@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_restore_native_value_then_optional_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
    frame_after_setup: dict[str, float] | None,
    expected_state: str,
) -> None:
    """Restored native_value persists; live frame overrides only when present.

    Covers four restore trajectories in one parametrize because they
    share the restore-setup → optional-frame → assert-state structure.
    Each id exercises a distinct path:

    - ``restored_only_before_first_frame`` — T3 native_value pin + T8
      pre-warm-window timing pin (state asserted at the pre-frame
      instant, after setup completes but before any explicit frame).
    - ``live_frame_overwrites_restored`` — T4. Live ``value_fn(frame)``
      non-None wins over ``_restored_native_value`` fallback.
    - ``live_frame_missing_field_preserves_restored`` — T5. Live
      ``value_fn(frame)`` is None (frame carries soc only, no voltage)
      → fallback to ``_restored_native_value`` keeps the restored
      reading surfaced rather than flipping to Unavailable.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_registry_keys=["voltage"],
        restored_states=[_voltage_restored_state()],
    )

    if frame_after_setup is not None:
        _push_frame(
            config_entry_with_vehicles,
            build_telemetry_frame(MOCK_VEHICLE_ID, **frame_after_setup),
        )
        await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_restore_last_reported_at_round_trips_as_datetime(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """Restored ISO ``last_reported_at`` parses back to ``datetime`` on the entity.

    The live coordinator stamps
    a ``datetime``; the recorder serialises via HA's ``JSONEncoder``
    (helpers/json.py:28-29) to an ISO string; the restore path parses
    that string back to ``datetime`` so the frontend's relative-time +
    history rendering treats it as a typed timestamp, not opaque text.

    Asserts both the runtime type (``isinstance(..., datetime)``) and
    the value (equals the original ``datetime`` we stuffed in).
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_registry_keys=["voltage"],
        restored_states=[_voltage_restored_state()],
    )

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    stamp = state.attributes.get("last_reported_at")
    assert isinstance(stamp, datetime)
    assert stamp == RESTORED_STAMP_DT


# ---------------------------------------------------------------------------
# T6 — Malformed restored stamp: attribute omitted entirely
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_malformed_restored_stamp_omits_attribute(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """Malformed stamp → ``last_reported_at`` ABSENT from attributes (not None).

    The ``datetime.fromisoformat(...)`` failure in the
    restore path must NOT set ``_restored_last_reported_at`` — the
    attribute is then OMITTED from ``extra_state_attributes``. Omit
    beats both expose-as-is ("Last reported: banana" in the UI) and
    ``None`` (renders as "Last reported: null").

    The native_value still restores: the malformed stamp affects only
    the stamp slot, not the value slot. This distinguishes "omit the
    bad field" from "lose all restoration".
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_registry_keys=["voltage"],
        restored_states=[_voltage_restored_state(last_reported_at="banana")],
    )

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    # Native value still restores — the malformed stamp doesn't
    # poison the value slot.
    assert state.state == str(RESTORED_VOLTAGE)
    # Stamp slot: attribute key must be ABSENT (omit-on-failure beats
    # propagating None).
    assert "last_reported_at" not in state.attributes


# ---------------------------------------------------------------------------
# T7 — last_reported_at stamps per-frame, NOT per merged-state
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_last_reported_at_stamps_per_frame_not_per_merged_state(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """Stamp refreshes only on frames whose ``value_fn`` returns non-None.

    The merge in ``apply_frame`` preserves voltage across frames that
    omit it (), so the
    merged-state's ``value_fn`` keeps returning the prior voltage. The
    stamp must NOT refresh on those bridging frames — otherwise the
    user reads "voltage last reported 2 minutes ago" when the upstream
    actually reported it 30 minutes ago, defeating the whole point of
    the attribute.

    The stamp loop runs on the UNMERGED frame's
    ``value_fn`` evaluation, not the merged state's. Three frames at
    distinct timestamps:

    1. t1 — frame with voltage=400 → stamp = t1.
    2. t2 — frame with soc only (no voltage) → stamp STILL t1.
    3. t3 — frame with voltage=410 → stamp = t3.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_registry_keys=["voltage"],
    )

    t1 = datetime(2026, 5, 24, 10, 0, 0, tzinfo=UTC)
    t2 = datetime(2026, 5, 24, 10, 5, 0, tzinfo=UTC)
    t3 = datetime(2026, 5, 24, 10, 10, 0, tzinfo=UTC)

    with freeze_time(t1):
        _push_frame(
            config_entry_with_vehicles,
            build_telemetry_frame(MOCK_VEHICLE_ID, voltage=400.0),
        )
        await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("last_reported_at") == t1

    with freeze_time(t2):
        # Frame WITHOUT voltage — merge preserves voltage=400 in the
        # merged state, but the stamp must not refresh because THIS
        # frame's value_fn(voltage) returns None.
        _push_frame(
            config_entry_with_vehicles,
            build_telemetry_frame(MOCK_VEHICLE_ID, soc=0.5),
        )
        await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("last_reported_at") == t1

    with freeze_time(t3):
        _push_frame(
            config_entry_with_vehicles,
            build_telemetry_frame(MOCK_VEHICLE_ID, voltage=410.0),
        )
        await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("last_reported_at") == t3


# ---------------------------------------------------------------------------
# Provider attribute on telemetry sensors (sensor surface)
# ---------------------------------------------------------------------------
#
# Symmetric reject contract: empty-string is malformed input, rejected on
# BOTH live and restore paths. The sensor's ``extra_state_attributes``
# composes ``provider`` alongside the existing ``last_reported_at`` with
# per-attribute live-wins-over-restored fallback. Restore guard mirrors
# the coordinator's ``_extract_provider`` boundary:
# ``isinstance(provider_raw, str) and provider_raw``.


def _voltage_frame_with_provider(
    voltage: float,
    *,
    provider: str | None = None,
) -> dict[str, Any]:
    """Construct a voltage telemetry frame; optionally embed ``provider``.

    Local helper rather than extending the shared
    :func:`tests.components.abetterrouteplanner.conftest.build_telemetry_frame`
    so that the existing fixture surface stays minimal — provider is
    sensor-specific. ``provider=None`` (the default) yields a frame
    without a ``provider`` key so downstream tests can mix-and-match
    "live frame, no provider" with "live frame, with provider" rows.
    """
    block: dict[str, Any] = {"v": voltage}
    if provider is not None:
        block["provider"] = provider
    return {"vehicleId": MOCK_VEHICLE_ID, "voltage": block}


# --- S1 -------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_provider_attribute_appears_from_live_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_seed_responses: AsyncMock,
) -> None:
    """A live frame carrying a provider exposes ``state.attributes["provider"]``.

    Cold install (no registry, no restore cache); the lazy-create
    dispatcher fires on the first non-None voltage frame and the entity
    immediately surfaces the provider string.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _restart_setup(hass, config_entry_with_vehicles)

    _push_frame(
        config_entry_with_vehicles,
        _voltage_frame_with_provider(400.0, provider=RESTORED_PROVIDER),
    )
    await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("provider") == RESTORED_PROVIDER


# --- S2 -------------------------------------------------------------------


@pytest.mark.parametrize(
    "live_provider",
    [
        pytest.param(None, id="frame_omits_provider"),
        pytest.param("", id="frame_empty_string_provider"),
    ],
)
@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_provider_attribute_absent_when_live_frame_lacks_provider(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_seed_responses: AsyncMock,
    live_provider: str | None,
) -> None:
    """No prior + frame without usable provider → ``provider`` key absent.

    Two cases collapse to one assertion under the symmetric-reject
    contract: a frame that omits the ``provider`` key AND a frame that
    carries ``"provider": ""`` are both treated as malformed — neither
    stamps the coordinator's ``last_provider`` map, neither surfaces as
    a user-visible attribute. The assertion is on attribute ABSENCE
    (``not in``) rather than ``is None``: a "present-but-null" leak
    would render as ``provider: null`` in templates and the dashboard.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _restart_setup(hass, config_entry_with_vehicles)

    _push_frame(
        config_entry_with_vehicles,
        _voltage_frame_with_provider(400.0, provider=live_provider),
    )
    await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert "provider" not in state.attributes


# --- S3 -------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_provider_attribute_restored_from_recorder_when_no_live_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """Restored ``provider`` surfaces even before any live frame arrives.

    Mirrors the existing restore-on-restart trajectory for the new
    provider slot. Pre-seed the recorder cache with both ``provider``
    and ``last_reported_at``; after restart + eager-from-registry, the
    entity exposes both restored attributes without depending on a
    wake-event frame to land.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_registry_keys=["voltage"],
        restored_states=[
            _voltage_restored_state(provider=RESTORED_PROVIDER),
        ],
    )

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("provider") == RESTORED_PROVIDER
    stamp = state.attributes.get("last_reported_at")
    assert isinstance(stamp, datetime)
    assert stamp == RESTORED_STAMP_DT


# --- S4 -------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_provider_per_attribute_live_wins_over_restored(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """Live and restored attributes compose per-attribute, not whole-mapping.

    The fallback from live to restored is per attribute, NOT whole
    dict. A
    live frame that carries ``voltage`` but omits ``provider`` must
    keep the restored ``provider`` AND pick up the live
    ``last_reported_at`` simultaneously. A whole-mapping fallback
    would mistakenly blank one or the other.

    Sequence:

    1. Restore with ``{provider: A, last_reported_at: T1}``.
    2. Setup (eager-from-registry creates entity carrying both restored).
    3. Live frame with voltage only (no provider) inside ``freeze_time(t2)``.
    4. Assert: ``provider == A`` (restored, sticky-on-omission),
       ``last_reported_at == t2`` (live wins on the stamp axis).
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_registry_keys=["voltage"],
        restored_states=[
            _voltage_restored_state(provider=RESTORED_PROVIDER),
        ],
    )

    t2 = datetime(2026, 5, 24, 14, 0, 0, tzinfo=UTC)
    with freeze_time(t2):
        _push_frame(
            config_entry_with_vehicles,
            _voltage_frame_with_provider(420.0, provider=None),
        )
        await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("provider") == RESTORED_PROVIDER
    assert state.attributes.get("last_reported_at") == t2
    # value-axis pin. A regression that decoupled value-publish
    # from attribute-publish (e.g. only refreshing `extra_state_attributes`
    # without re-evaluating ``native_value``) would slip past the
    # attribute-only assertions above. Pin the underlying live voltage
    # surfaces on ``state.state`` for the same frame.
    assert float(state.state) == 420.0


# --- S5 + S6 (parametrised — symmetric malformed-restore rejection) -------


@pytest.mark.parametrize(
    "restored_provider",
    [
        pytest.param("", id="restored_empty_string"),
        pytest.param(123, id="restored_int"),
        pytest.param(True, id="restored_bool"),
        pytest.param({"nested": "dict"}, id="restored_dict"),
        pytest.param([1, 2, 3], id="restored_list"),
        pytest.param(None, id="restored_none"),
        # whitespace shapes — REJECT-ONLY.
        # Single contract with the wire boundary's ``_extract_provider``
        # rejection (see test_coordinator.py parametrize). Restored
        # provider passes the same `isinstance(_, str) and _.strip()`
        # guard, so whitespace-only is malformed and leading/trailing
        # whitespace on an otherwise-valid token is rejected as
        # non-canonical wire shape — the symmetric-reject contract
        # extended to whitespace.
        pytest.param("   ", id="restored_whitespace_only_spaces"),
        pytest.param("\t\n", id="restored_whitespace_only_tabs_newlines"),
        pytest.param(
            "  RIVIAN_STREAM  ",
            id="restored_leading_trailing_whitespace",
        ),
    ],
)
@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_provider_attribute_absent_when_restored_value_malformed(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
    restored_provider: Any,
) -> None:
    """Malformed restored ``provider`` → attribute OMITTED entirely on the entity.

    Symmetric reject: the restore guard rejects every shape that the
    live-path ``_extract_provider`` would also reject — empty string,
    integers, bools, dicts, lists, ``None``. The fallback is "no
    provider attribute", NOT a present-with-null leak. The
    ``last_reported_at`` slot survives unaffected (this distinguishes
    "omit the bad field" from "lose all restoration").

    Per  the
    negation is asserted via ``"provider" not in state.attributes``;
    ``last_reported_at`` survives as the trigger pin so a regression that
    blanked the entire ``extra_state_attributes`` dict would also fail
    the second assertion.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_registry_keys=["voltage"],
        restored_states=[_voltage_restored_state(provider=restored_provider)],
    )

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert "provider" not in state.attributes
    # ``last_reported_at`` slot is independent — malformed provider
    # must not collapse the whole attribute dict.
    stamp = state.attributes.get("last_reported_at")
    assert isinstance(stamp, datetime)
    assert stamp == RESTORED_STAMP_DT


# ---------------------------------------------------------------------------
# T6 — vehicle-removed-mid-restore (sensor mirror of tracker T8)
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_deselected_vehicle_skips_eager_create_with_restore_cache(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """Registry has voltage entry + recorder has voltage state but CONF_VEHICLE_IDS = [] → skip.

    Sensor mirror of ``test_deselected_vehicle_skips_eager_create`` in
    ``test_restore_gps.py``. User reconfigured to deselect this vehicle
    between sessions; the entity_registry still holds the row, the
    recorder still holds the last value — but the eager-create probe's
    ``vehicle.vehicle_id not in selected_ids`` filter must reject and
    the integration must NOT spuriously surface a sensor for an
    unselected vehicle.

    Defense-in-depth pin: composes with
     — the real cleanup happens via
    ``_remove_stale_devices`` on the next garage-coordinator poll, but
    the eager-create filter is the same-cycle safety net so the user
    never sees a ghost sensor row during the 10 min between deselect
    and the next poll.

    Asserts whole-state ABSENCE rather than ``is None`` on a specific
    attribute — a regression that
    half-created the entity (registry row + state object, no
    native_value) would still fail this assertion.
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
        preseed_registry_keys=["voltage"],
        restored_states=[_voltage_restored_state()],
    )

    # Eager-create branch must NOT add the sensor even though the
    # registry row + restore cache both exist — the vehicle is no longer
    # selected and the filter rejects.
    assert hass.states.get(VOLTAGE_ENTITY_ID) is None


# ---------------------------------------------------------------------------
# T9 — pre-warm-before-predicates stamp invariant
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client")
async def test_frame_during_prewarm_stamps_attrs_for_eager_created_entity(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
    mock_sse_client: AsyncMock,
) -> None:
    """Frames arriving during pre-warm correctly stamp both attribute slots.

    Per  and
    : ``STAMPED_VALUE_FNS``
    is a module-level constant, populated at import time, so the
    stamp loop in ``apply_frame`` runs BEFORE the sensor platform
    registers presence predicates. A frame that arrives during the
    pre-warm window (after SSE consumer spins up, before
    ``register_presence_predicates`` is called) must:

    1. Land its value in ``coordinator.data`` (merge invariant).
    2. Stamp ``last_reported_at[vid][key]``.
    3. Stamp ``last_provider[vid][key]``.

    All three before the predicate-registration crossover that gates
    LAZY dispatcher creation. EAGER-from-registry creation (the
    ``preseed_registry_keys`` path) inherits all three on its first
    property read — no race against the predicate-registration order.

    GREEN-on-arrival defense-in-depth pin . A future
    refactor that moved the stamp loop into the predicate-dispatch
    branch (re-conflating pre-warm with predicate registration) would
    fail this assertion: stamps would only fire AFTER platform setup,
    and the eager-from-registry entity would surface with no
    attributes despite the frame having landed.

    The ``mock_sse_client.set_frames(...)`` pre-queues frames into the
    SSE consumer's iterator BEFORE ``async_setup_entry`` starts; the
    consumer task picks them up at its first ``__anext__`` and routes
    them through ``apply_frame``. ``async_block_till_done`` flushes
    the consumer's first iteration so the assertions see the merged
    state by the time setup returns.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}
    mock_sse_client.set_frames(
        [
            {
                "vehicleId": MOCK_VEHICLE_ID,
                "voltage": {"v": 405.0, "provider": "RIVIAN_STREAM"},
            }
        ]
    )

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_registry_keys=["voltage"],
    )

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert float(state.state) == 405.0
    stamp = state.attributes.get("last_reported_at")
    assert isinstance(stamp, datetime)
    assert state.attributes.get("provider") == "RIVIAN_STREAM"


# ---------------------------------------------------------------------------
# malformed restored native_value → entity unavailable
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_native_value",
    [
        pytest.param("not-a-number", id="non_numeric_string"),
        pytest.param(True, id="bool_true"),
        pytest.param(False, id="bool_false"),
        pytest.param({"nested": "dict"}, id="dict"),
        pytest.param([1, 2], id="list"),
    ],
)
@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_restored_native_value_rejected_when_malformed(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
    bad_native_value: Any,
) -> None:
    """Malformed restored ``native_value`` + no live frame → entity unavailable.

    Shape-class parametrize, not per-registry-entry. The guard at
    ``sensor.py``:
    ``isinstance(value, (int, float)) and not isinstance(value, bool)``
    is uniform across the 10 telemetry sensors — walking every registry
    entry adds noise without coverage. One sensor (voltage) × 5
    adversarial shapes is the right floor.

    All 5 cases are GREEN-on-arrival regression pins: the existing
    isinstance guard already rejects each shape today, but the explicit
    "rejection ⇒ entity Unavailable" assertion is new (the entity
    surface is implicitly covered by the ``available`` property's
    ``self.native_value is not None`` check; pin makes it explicit so a
    future refactor that admits the malformed value through a different
    code path fails loudly).

    The entity eager-creates from the registry preseed (no live frame
    after setup), so its state depends solely on
    ``_restored_native_value``. Malformed → slot stays None →
    ``native_value`` returns None → ``available`` returns False →
    ``state.state == "unavailable"``.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_registry_keys=["voltage"],
        restored_states=[_voltage_restored_state(native_value=bad_native_value)],
    )

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.state == "unavailable"


# ---------------------------------------------------------------------------
# eager-create probe skips registry rows owned by a foreign entry
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_foreign_config_entry_voltage_row_skipped_by_eager_probe(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    token_entry: dict[str, Any],
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """Eager-create probe MUST filter on ``config_entry_id`` — foreign rows skipped.

    Probe finding: The ABRP ``unique_id``
    scope formula uses ``entry.unique_id`` (OIDC ``sub``), not
    ``entry.entry_id``. Two simultaneous config_entries with the same
    OIDC ``sub`` would compute the same ``unique_id`` for the same
    vehicle. Today's config-flow ``_abort_if_unique_id_configured``
    makes that impossible — but defense-in-depth against any future
    change that admits multiple entries per ``sub``.

    Pre-seed setup:
    - A *foreign* MockConfigEntry exists in the registry, owning a
      voltage row with the same unique_id formula the entry-under-test
      would compute.
    - The entry-under-test (``config_entry_with_vehicles``) has the same
      OIDC sub + the same vehicle selected.

    GREEN-on-arrival regression pin. HA core's entity_platform
    incidentally blocks today: the foreign
    entry's full ``async_setup`` runs first (via ``add_to_hass``),
    claims the entity_id, so the under-test entry's eager-probe
    ``async_add_entities`` call is silently rejected by HA core's
    duplicate-entity-id guard and the foreign row's
    ``config_entry_id`` survives. The defensive filter the dev will
    add moves the same outcome from "HA core happens to block" to
    "integration boundary deterministically rejects", insulating from
    a future HA core change that admits the rebind (e.g.
    ``async_get_or_create`` favouring newer-entry over older). The
    filter preempts that regression at the integration boundary.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    # Foreign entry — same OIDC sub (so unique_id collides), different
    # entry_id. Added to hass so the registry accepts the row.
    foreign_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SENSOR_TEST_SUB,
        entry_id="01FOREIGNENTRYIDXXXXXXXXXX",
        data={
            "auth_implementation": DOMAIN,
            "token": token_entry,
            CONF_VEHICLE_IDS: [str(MOCK_VEHICLE_ID)],
        },
    )
    foreign_entry.add_to_hass(hass)
    # Seed the foreign entry's voltage registry row using the SAME
    # unique_id formula the entry-under-test would compute.
    foreign_row = entity_registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id=f"{SENSOR_TEST_SUB}_{MOCK_VEHICLE_ID}_voltage",
        config_entry=foreign_entry,
        suggested_object_id="rivian_r2_2027_standard_long_range_voltage",
    )

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        # No preseed via _restart_setup — the foreign row above is the
        # only registry entry for this unique_id. The eager-create
        # probe must look up by unique_id, fetch the row, see foreign
        # config_entry_id, and skip.
    )

    # Foreign row's attribution stays foreign — the entry-under-test
    # did NOT silently re-claim it via the eager probe's rebind path.
    #
    # GREEN-on-arrival regression pin. HA core's entity_platform
    # currently blocks the rebind because the
    # foreign entry's setup runs first and claims the entity_id, so the
    # under-test eager probe's ``async_add_entities`` call is silently
    # rejected by entity_id collision and the foreign row's
    # ``config_entry_id`` survives. The defensive filter the dev will
    # add (post-``async_get_entity_id`` lookup, filter on
    # ``config_entry_id``) makes the same outcome deterministic at the
    # INTEGRATION boundary rather than relying on HA core's downstream
    # rejection. A future HA core change that allowed the rebind
    # (e.g. ``async_get_or_create`` choosing newer-config-entry over
    # older) would silently regress today's accidental-safety; the
    # filter preempts that. RED iff the dev's filter is later removed
    # AND HA core stops blocking the rebind.
    refetched = entity_registry.async_get(foreign_row.entity_id)
    assert refetched is not None
    assert refetched.config_entry_id == foreign_entry.entry_id
