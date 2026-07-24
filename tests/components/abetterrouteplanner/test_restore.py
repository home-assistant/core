"""Tests for sensor state restoration across HA restart.

Covers the recorder-backed restoration path on the aioabrp telemetry driver:
the typed coordinator surfaces (``data`` / ``last_reported_at`` /
``last_provider``) feed the sensor's live-wins-over-restored composition, and
``RestoreSensor`` + the eager-from-registry probe lift the recorder's last
value / stamp / provider back onto the entity across a restart.

Telemetry state is now typed: the coordinator holds
``dict[int, dict[Metric, MetricValue]]`` and the library
(:class:`aioabrp.TelemetryStream`) owns wire parsing, reconnect, merge and
monotonicity. These tests cover only the HA-side restore + per-attribute
live-wins contract:

- Cold install (no prior registry, no restore cache): lazy contract
  preserved — no eager-create bleed onto fresh installs.
- Restart with prior entity-registry entry: eager-create from the
  registry probe BEFORE the first live frame.
- Restore + optional live-frame interaction (parametrized):
  ``native_value`` persists across restart, a live frame overwrites,
  a frame missing the metric preserves the restored value.
- ``extra_state_attributes["last_reported_at"]`` round-trips the recorder's
  ISO string back to a ``datetime``.
- Malformed restored stamp ("banana"): attribute omitted entirely
  (not present-with-None).
- ``provider`` attribute: live appearance, live-absence omission, restore,
  per-attribute live-wins (live stamp + restored sticky provider), and the
  symmetric malformed-restore rejection guard.
- Malformed restored ``native_value`` → entity unavailable.

The seed path is driven by ``mock_abrp_client.seed_responses``; the live
path is driven by ``fake_stream.fire_frame`` (a synchronous double for the
real ``TelemetryStream``). The coordinator stamps ``last_reported_at`` with
``dt_util.utcnow()`` at the moment a frame is applied (RECEIPT time, NOT the
wire ``MetricValue.time``), so tests that need a deterministic stamp wrap
``fire_frame`` in ``freeze_time`` — the stamp then equals the frozen instant.

Wire-frame parsing and frame merge / monotonicity are now library-owned
(covered by aioabrp's own tests), so the legacy
``test_last_reported_at_stamps_per_frame_not_per_merged_state`` keeps only its
HA-side claim (``_apply_metrics`` stamps per metric IN the batch, not per
merged-state).
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

from aioabrp import Telemetry
from freezegun import freeze_time
import pytest

from homeassistant.components.abetterrouteplanner.const import CONF_VEHICLE_IDS, DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import (
    MOCK_VEHICLE_ID,
    MOCK_VEHICLE_ID_2,
    SENSOR_TEST_SUB,
    build_metric_value,
)

from tests.common import MockConfigEntry, mock_restore_cache_with_extra_data

VOLTAGE_ENTITY_ID = "sensor.rivian_r2_2027_standard_long_range_voltage"

# Provider sentinel for "this restore-state should omit the ``provider``
# attribute entirely" — distinct from passing the literal ``None`` value
# (which would land as a present-but-null attribute).
_PROVIDER_UNSET: Any = object()

RESTORED_PROVIDER = "RIVIAN_STREAM"

# Restored slot anchors. Times chosen so freeze_time ranges in the
# per-frame-stamp test are visibly disjoint from this baseline in failure
# traces.
RESTORED_VOLTAGE = 410.0
RESTORED_STAMP_ISO = "2026-05-20T12:00:00+00:00"
RESTORED_STAMP_DT = datetime(2026, 5, 20, 12, 0, 0, tzinfo=UTC)


def _fire_voltage(
    entry: MockConfigEntry,
    fake_stream: Any,
    voltage: float,
    *,
    provider: str | None = None,
) -> None:
    """Drive a single-voltage live frame through the fake telemetry stream.

    Mirrors what a real ``TelemetryStream`` would push: a typed
    ``{Metric.VOLTAGE: MetricValue}`` batch routed to the coordinator's
    ``on_update``. The coordinator stamps ``last_reported_at`` with the
    receipt time (``dt_util.utcnow()``) at apply, so wrapping the call in
    ``freeze_time`` pins the stamp deterministically.
    """
    assert entry.runtime_data is not None  # entry set up before firing.
    fake_stream.fire_frame(
        MOCK_VEHICLE_ID,
        Telemetry(voltage=build_metric_value(voltage, provider=provider)),
    )


def _voltage_restored_state(
    *,
    native_value: float | None = RESTORED_VOLTAGE,
    last_reported_at: str | None = RESTORED_STAMP_ISO,
    provider: Any = _PROVIDER_UNSET,
) -> tuple[State, dict[str, Any]]:
    """Build a (State, extra_data) tuple for ``mock_restore_cache_with_extra_data``.

    ``last_reported_at`` is supplied as an ISO string mirroring what the
    recorder serialises from a ``datetime`` via HA's ``JSONEncoder``. The
    restore path is expected to parse it back to a ``datetime`` via
    ``datetime.fromisoformat`` on the stored string; on parse failure the
    attribute is OMITTED, not surfaced as ``None``.

    ``provider`` defaults to the sentinel :data:`_PROVIDER_UNSET` which keeps
    the attribute absent from the State for callers that do not care about the
    provider slot. Passing any concrete value (string, int, None, empty
    string, etc.) lands it under the ``provider`` key in ``State.attributes``
    so the integration's restore path exercises its type-guard branch.
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

    Sequence:

    1. ``hass.set_state(CoreState.not_running)`` — required for
       ``RestoreEntity`` / ``RestoreSensor`` to surface its cache.
    2. ``mock_restore_cache_with_extra_data(...)`` — wire the recorder
       cache so ``async_get_last_sensor_data`` returns prior values.
    3. ``entry.add_to_hass`` + optional entity-registry pre-seeding so
       the eager-from-registry branch finds prior entries.
    4. The ``fake_stream`` fixture (a required usefixtures on every caller)
       patches ``TelemetryStream`` with a synchronous double, so setup
       completes without a real SSE consumer.
    5. ``EVENT_HOMEASSISTANT_STARTED`` fired at the end so any post-start
       hooks settle before assertions run.
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
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_cold_install_lazy_create_preserved(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """Cold install: no registry, no seed, no frame → no entity yet; frame creates.

    Negation-then-trigger oracle: pins that the eager-from-registry
    branch does NOT spuriously create entities at setup when no prior
    registry row exists. The first non-None voltage frame then triggers
    lazy creation via the dispatcher — the lazy-creation contract must
    survive across HA restart unbroken.
    """
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = Telemetry()

    await _restart_setup(hass, config_entry_with_vehicles)

    # Negation: no prior registry → no eager-create at setup.
    assert hass.states.get(VOLTAGE_ENTITY_ID) is None

    # Trigger: first voltage frame fires the dispatcher → entity created.
    _fire_voltage(config_entry_with_vehicles, fake_stream, 400.0)
    await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.state == "400.0"


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_restart_eager_create_from_registry(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
) -> None:
    """Prior voltage registry entry → entity eager-created BEFORE any frame.

    Addresses the user-confirmed bug (16h Unavailable on parked
    vehicles). The setup-time registry probe must instantiate the entity
    even when no live or seed frame carries the field, so the user's UI
    shows a sensor row immediately on restart rather than after the next
    wake event.

    No restore cache is wired here — the entity exists but its
    ``native_value`` falls back to ``None`` until the next frame
    (acceptable degradation for the "registry present but recorder
    pruned" path).
    """
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = Telemetry()

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


@pytest.mark.parametrize(
    ("live_voltage", "expected_state"),
    [
        pytest.param(
            None, str(RESTORED_VOLTAGE), id="restored_only_before_first_frame"
        ),
        pytest.param(420.0, "420.0", id="live_frame_overwrites_restored"),
    ],
)
@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_restore_native_value_then_optional_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
    live_voltage: float | None,
    expected_state: str,
) -> None:
    """Restored native_value persists; a live voltage frame overrides it.

    Two restore trajectories share the restore-setup → optional-frame →
    assert-state structure:

    - ``restored_only_before_first_frame`` — native_value pin at the
      pre-frame instant (setup complete, no live frame yet): the restored
      value surfaces.
    - ``live_frame_overwrites_restored`` — a live ``MetricValue`` for
      voltage wins over the ``_restored_native_value`` fallback.

    The "live frame for a DIFFERENT metric preserves the restored voltage"
    trajectory is no longer expressible the same way: ``fire_frame`` applies
    only the metrics in its typed batch, so a frame carrying soc never
    touches the voltage slot — that preservation is implicit in the typed
    per-metric model and covered by the per-metric-stamp test below.
    """
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = Telemetry()

    await _restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_registry_keys=["voltage"],
        restored_states=[_voltage_restored_state()],
    )

    if live_voltage is not None:
        _fire_voltage(config_entry_with_vehicles, fake_stream, live_voltage)
        await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_restore_last_reported_at_round_trips_as_datetime(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
) -> None:
    """Restored ISO ``last_reported_at`` parses back to ``datetime`` on the entity.

    The live coordinator stamps a ``datetime``; the recorder serialises via
    HA's ``JSONEncoder`` to an ISO string; the restore path parses that
    string back to ``datetime`` so the frontend's relative-time + history
    rendering treats it as a typed timestamp, not opaque text.

    Asserts both the runtime type (``isinstance(..., datetime)``) and the
    value (equals the original ``datetime`` we stuffed in).
    """
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = Telemetry()

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


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_malformed_restored_stamp_omits_attribute(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
) -> None:
    """Malformed stamp → ``last_reported_at`` ABSENT from attributes (not None).

    The ``datetime.fromisoformat(...)`` failure in the restore path must NOT
    set ``_restored_last_reported_at`` — the attribute is then OMITTED from
    ``extra_state_attributes``. Omit beats both expose-as-is ("Last reported:
    banana" in the UI) and ``None`` (renders as "Last reported: null").

    The native_value still restores: the malformed stamp affects only the
    stamp slot, not the value slot. This distinguishes "omit the bad field"
    from "lose all restoration".
    """
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = Telemetry()

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


@pytest.mark.usefixtures("mock_abrp_client")
async def test_last_reported_at_stamps_per_metric_not_per_merged_state(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """Stamp refreshes only on frames whose batch carries the voltage metric.

    The coordinator's ``_apply_metrics`` stamps ``last_reported_at`` per
    metric IN the applied batch — a frame that omits voltage leaves the
    voltage data AND its stamp untouched (the library owns cross-frame merge;
    the HA-side coordinator only stamps what each batch carries). The stamp
    must NOT refresh on a bridging frame for a different metric — otherwise
    the user reads "voltage last reported 2 minutes ago" when the upstream
    actually reported it 30 minutes ago, defeating the attribute.

    Three frames at distinct frozen receipt instants:

    1. t1 — voltage=400 → stamp = t1.
    2. t2 — soc only (no voltage) → voltage stamp STILL t1.
    3. t3 — voltage=410 → stamp = t3.

    Receipt-time determinism: the coordinator stamps ``dt_util.utcnow()`` at
    apply, so each ``fire_frame`` is wrapped in ``freeze_time`` to pin the
    stamp to a known instant.
    """
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = Telemetry()

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
        fake_stream.fire_frame(
            MOCK_VEHICLE_ID, Telemetry(voltage=build_metric_value(400.0))
        )
        await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("last_reported_at") == t1

    with freeze_time(t2):
        # Frame for a DIFFERENT metric — the batch carries soc only, so the
        # voltage slot AND its stamp are untouched.
        fake_stream.fire_frame(MOCK_VEHICLE_ID, Telemetry(soc=build_metric_value(50.0)))
        await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("last_reported_at") == t1

    with freeze_time(t3):
        fake_stream.fire_frame(
            MOCK_VEHICLE_ID, Telemetry(voltage=build_metric_value(410.0))
        )
        await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("last_reported_at") == t3


# Symmetric reject contract: empty-string / padded / non-str is malformed
# input, rejected on BOTH live and restore paths. The sensor's
# ``extra_state_attributes`` composes ``provider`` alongside
# ``last_reported_at`` with per-attribute live-wins-over-restored fallback.


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_provider_attribute_appears_from_live_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """A live frame carrying a provider exposes ``state.attributes["provider"]``.

    Cold install (no registry, no restore cache); the lazy-create dispatcher
    fires on the first non-None voltage frame and the entity immediately
    surfaces the provider string.
    """
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = Telemetry()

    await _restart_setup(hass, config_entry_with_vehicles)

    _fire_voltage(
        config_entry_with_vehicles, fake_stream, 400.0, provider=RESTORED_PROVIDER
    )
    await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("provider") == RESTORED_PROVIDER


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_provider_attribute_absent_when_live_frame_lacks_provider(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """No prior + frame without a provider → ``provider`` key absent.

    A ``MetricValue`` with ``provider=None`` does not stamp the coordinator's
    ``last_provider`` map (sticky-on-omission with no prior value), so the
    sensor surfaces no provider attribute. The assertion is on attribute
    ABSENCE (``not in``) rather than ``is None``: a "present-but-null" leak
    would render as ``provider: null`` in templates and the dashboard.

    The empty-string wire shape is a library-boundary rejection now (the
    library only emits a typed ``MetricValue`` with a clean provider or
    ``None``), so this HA-side test exercises the ``None`` case only.
    """
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = Telemetry()

    await _restart_setup(hass, config_entry_with_vehicles)

    _fire_voltage(config_entry_with_vehicles, fake_stream, 400.0, provider=None)
    await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert "provider" not in state.attributes


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_provider_attribute_restored_from_recorder_when_no_live_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
) -> None:
    """Restored ``provider`` surfaces even before any live frame arrives.

    Mirrors the restore-on-restart trajectory for the provider slot. Pre-seed
    the recorder cache with both ``provider`` and ``last_reported_at``; after
    restart + eager-from-registry, the entity exposes both restored attributes
    without depending on a wake-event frame to land.
    """
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = Telemetry()

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


@pytest.mark.usefixtures("mock_abrp_client")
async def test_provider_per_attribute_live_wins_over_restored(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """Live and restored attributes compose per-attribute, not whole-mapping.

    The fallback from live to restored is per attribute, NOT whole dict. A
    live frame that carries ``voltage`` but omits ``provider`` must keep the
    restored ``provider`` AND pick up the live ``last_reported_at``
    simultaneously. A whole-mapping fallback would mistakenly blank one or
    the other.

    Sequence:

    1. Restore with ``{provider: A, last_reported_at: T1}``.
    2. Setup (eager-from-registry creates entity carrying both restored).
    3. Live frame with voltage only (provider=None) inside ``freeze_time(t2)``.
    4. Assert: ``provider == A`` (restored, sticky-on-omission),
       ``last_reported_at == t2`` (live wins on the stamp axis).
    """
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = Telemetry()

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
        _fire_voltage(config_entry_with_vehicles, fake_stream, 420.0, provider=None)
        await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("provider") == RESTORED_PROVIDER
    assert state.attributes.get("last_reported_at") == t2
    # value-axis pin. A regression that decoupled value-publish from
    # attribute-publish (e.g. only refreshing ``extra_state_attributes``
    # without re-evaluating ``native_value``) would slip past the
    # attribute-only assertions above. Pin the underlying live voltage
    # surfaces on ``state.state`` for the same frame.
    assert float(state.state) == 420.0


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
        # Restored provider passes the same ``_is_clean_provider_str`` guard
        # (``isinstance(_, str) and _ and _ == _.strip()``), so whitespace-only
        # is malformed and leading/trailing whitespace on an otherwise-valid
        # token is rejected as non-canonical wire shape — the symmetric-reject
        # contract extended to whitespace.
        pytest.param("   ", id="restored_whitespace_only_spaces"),
        pytest.param("\t\n", id="restored_whitespace_only_tabs_newlines"),
        pytest.param(
            "  RIVIAN_STREAM  ",
            id="restored_leading_trailing_whitespace",
        ),
    ],
)
@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_provider_attribute_absent_when_restored_value_malformed(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    restored_provider: Any,
) -> None:
    """Malformed restored ``provider`` → attribute OMITTED entirely on the entity.

    Symmetric reject: the restore guard (``_is_clean_provider_str``) rejects
    every shape that the live-path provider extraction would also reject —
    empty string, integers, bools, dicts, lists, ``None``, whitespace-only,
    and padded tokens. The fallback is "no provider attribute", NOT a
    present-with-null leak. The ``last_reported_at`` slot survives unaffected
    (this distinguishes "omit the bad field" from "lose all restoration").
    """
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = Telemetry()

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


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_deselected_vehicle_skips_eager_create_with_restore_cache(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
) -> None:
    """Registry + recorder hold a voltage row but CONF_VEHICLE_IDS = [] → skip.

    User reconfigured to deselect this vehicle between sessions; the
    entity_registry still holds the row, the recorder still holds the last
    value — but the eager-create probe's ``vehicle.vehicle_id not in
    selected_ids`` filter must reject and the integration must NOT spuriously
    surface a sensor for an unselected vehicle.

    Asserts whole-state ABSENCE rather than ``is None`` on a specific
    attribute — a regression that half-created the entity (registry row +
    state object, no native_value) would still fail this assertion.
    """
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = Telemetry()
    # Entry exists but CONF_VEHICLE_IDS is empty (user just deselected this
    # vehicle).
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
@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_restored_native_value_rejected_when_malformed(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    bad_native_value: Any,
) -> None:
    """Malformed restored ``native_value`` + no live frame → entity unavailable.

    Shape-class parametrize, not per-registry-entry. The guard in
    ``AbrpNumericSensor._restore_native_value``
    (``isinstance(value, (int, float)) and not isinstance(value, bool)``)
    is uniform across the numeric telemetry sensors — walking every registry
    entry adds noise without coverage. One sensor (voltage) x 5 adversarial
    shapes is the right floor.

    The entity eager-creates from the registry preseed (no live frame after
    setup), so its state depends solely on ``_restored_native_value``.
    Malformed → slot stays None → ``native_value`` returns None →
    ``available`` returns False → ``state.state == "unavailable"``.
    """
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = Telemetry()

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


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_foreign_config_entry_voltage_row_skipped_by_eager_probe(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    token_entry: dict[str, Any],
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
) -> None:
    """Eager-create probe MUST filter on ``config_entry_id`` — foreign rows skipped.

    The ABRP ``unique_id`` scope formula uses ``entry.unique_id`` (OIDC
    ``sub``), not ``entry.entry_id``. Two simultaneous config_entries with the
    same OIDC ``sub`` would compute the same ``unique_id`` for the same
    vehicle. Today's config-flow ``_abort_if_unique_id_configured`` makes that
    impossible — but defense-in-depth against any future change that admits
    multiple entries per ``sub``.

    Pre-seed setup:
    - A *foreign* MockConfigEntry exists in the registry, owning a voltage row
      with the same unique_id formula the entry-under-test would compute.
    - The entry-under-test (``config_entry_with_vehicles``) has the same OIDC
      sub + the same vehicle selected.

    The eager-probe's ``entry_row.config_entry_id != entry.entry_id`` filter
    must skip the foreign row so the foreign row's attribution survives.
    """
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = Telemetry()

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
        # only registry entry for this unique_id. The eager-create probe
        # must look up by unique_id, fetch the row, see foreign
        # config_entry_id, and skip.
    )

    # Foreign row's attribution stays foreign — the entry-under-test did NOT
    # silently re-claim it via the eager probe's rebind path. The defensive
    # filter (post-``async_get_entity_id`` lookup, filter on
    # ``config_entry_id``) makes the outcome deterministic at the integration
    # boundary.
    refetched = entity_registry.async_get(foreign_row.entity_id)
    assert refetched is not None
    assert refetched.config_entry_id == foreign_entry.entry_id


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_setup_polls_new_vehicle_without_registered_sensors(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    fake_stream: Any,
) -> None:
    """A selected vehicle with NO registry rows is polled once at setup.

    Fresh install / newly-added vehicle: there is no prior sensor entity in the
    registry, so ``vehicles_without_sensors`` flags it as new and
    ``async_setup_entry`` runs the one-shot ``async_get_current_telemetry`` poll
    for it. The stream is constructed WITHOUT a ``seed=`` kwarg (the HA-side
    gate-seed machinery is gone), so the captured ``seed`` is ``None``.
    """

    async def _record_poll(vehicle_id: int) -> Telemetry:
        return Telemetry()

    with patch(
        "aioabrp.AbrpClient.async_get_current_telemetry",
        side_effect=_record_poll,
    ) as mock_poll:
        await _restart_setup(hass, config_entry_with_vehicles)

    # New vehicle (no registered sensors) → the one-shot poll ran for it.
    polled_ids = {call.args[0] for call in mock_poll.call_args_list}
    assert polled_ids == {MOCK_VEHICLE_ID}

    # The stream is constructed without a gate seed.
    stream = fake_stream.stream
    assert stream is not None
    assert stream.seed is None


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_setup_skips_poll_for_known_vehicle_with_registered_sensor(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    fake_stream: Any,
) -> None:
    """A selected vehicle WITH a registered sensor is NOT polled at setup.

    The vehicle already has a voltage sensor row in the entity registry, so the
    eager-from-registry probe + ``RestoreSensor`` recreate its entities and
    restore their last values. ``vehicles_without_sensors`` therefore omits it
    and ``async_setup_entry`` skips the one-shot poll. The stream still carries
    no gate seed.
    """

    async def _record_poll(vehicle_id: int) -> Telemetry:
        return Telemetry()

    with patch(
        "aioabrp.AbrpClient.async_get_current_telemetry",
        side_effect=_record_poll,
    ) as mock_poll:
        await _restart_setup(
            hass,
            config_entry_with_vehicles,
            entity_registry=entity_registry,
            preseed_registry_keys=["voltage"],
        )

    # Known vehicle (a registered sensor exists) → no one-shot poll.
    assert mock_poll.call_count == 0

    # The stream is constructed without a gate seed.
    stream = fake_stream.stream
    assert stream is not None
    assert stream.seed is None


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_setup_polls_only_new_vehicle_in_mixed_garage(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    entity_registry: er.EntityRegistry,
    fake_stream: Any,
) -> None:
    """Mixed garage: only the new vehicle is polled; the known one is skipped.

    Two selected vehicles: ``MOCK_VEHICLE_ID`` has a registered voltage sensor
    (known → restored via the eager probe + ``RestoreSensor``), while
    ``MOCK_VEHICLE_ID_2`` has none (new). ``async_setup_entry`` must poll
    EXACTLY the new vehicle, never the known one, and both selected/present
    vehicles are still streamed without a gate seed.
    """
    # Two-vehicle entry (same SENSOR_TEST_SUB scope so the registry unique_id
    # formula matches), selecting BOTH garage vehicles.
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SENSOR_TEST_SUB,
        data={
            "auth_implementation": DOMAIN,
            "token": token_entry,
            CONF_VEHICLE_IDS: [str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)],
        },
    )

    async def _record_poll(vehicle_id: int) -> Telemetry:
        return Telemetry()

    with patch(
        "aioabrp.AbrpClient.async_get_current_telemetry",
        side_effect=_record_poll,
    ) as mock_poll:
        # ``_restart_setup`` preseeds a voltage registry row for
        # MOCK_VEHICLE_ID only, leaving MOCK_VEHICLE_ID_2 with no sensors.
        await _restart_setup(
            hass,
            entry,
            entity_registry=entity_registry,
            preseed_registry_keys=["voltage"],
        )

    # The poll ran for EXACTLY the new vehicle — never the known one.
    polled_ids = {call.args[0] for call in mock_poll.call_args_list}
    assert polled_ids == {MOCK_VEHICLE_ID_2}

    # Both selected (and present) vehicles are still streamed, no gate seed.
    stream = fake_stream.stream
    assert stream is not None
    assert stream.seed is None
    assert set(stream.vehicle_ids) == {MOCK_VEHICLE_ID, MOCK_VEHICLE_ID_2}
