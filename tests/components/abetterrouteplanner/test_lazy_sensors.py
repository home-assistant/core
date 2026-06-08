"""Tests for lazy/dispatcher entity creation with SSE pre-warm.

Eight observable-contract tests plus one absence guard.

Pre-warm window
~~~~~~~~~~~~~~~
``async_setup_entry`` waits ``PREWARM_WINDOW_SECONDS`` between SSE spawn and
platform forward. Tests that do not exercise the timing of that window patch
the constant to ``0`` so setup returns immediately, while leaving
``asyncio.sleep`` untouched so the SSE retry backoff continues to use a real
sleep (see ``project_abrp_asyncio_sleep_test_patching`` memory).
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.abetterrouteplanner import AbrpData
from homeassistant.components.abetterrouteplanner.const import CONF_VEHICLE_IDS, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import (
    MOCK_VEHICLE_ID,
    MOCK_VEHICLE_ID_2,
    SENSOR_TEST_SUB,
    build_telemetry_frame,
)

from tests.common import MockConfigEntry

# Entity IDs for vehicle 1 (Rivian R2 2027 Standard Long Range)
SOC_ENTITY_ID = "sensor.rivian_r2_2027_standard_long_range_soc"
POWER_ENTITY_ID = "sensor.rivian_r2_2027_standard_long_range_power"
VOLTAGE_ENTITY_ID = "sensor.rivian_r2_2027_standard_long_range_voltage"

# Entity IDs for vehicle 2 (Rivian R1S 2024 Quad Max)
VOLTAGE_ENTITY_ID_2 = "sensor.rivian_r1s_2024_quad_max_voltage"


def _push_frame(entry: MockConfigEntry, frame: dict[str, Any]) -> None:
    """Inject a synthesized telemetry frame through the coordinator boundary."""
    runtime_data: AbrpData = entry.runtime_data
    runtime_data.telemetry_coordinator.apply_frame(frame)


async def _lazy_setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the integration with the pre-warm window collapsed to zero.

    Patches ``PREWARM_WINDOW_SECONDS`` (not ``asyncio.sleep``) so the SSE
    retry backoff loop in ``_run_sse_loop`` keeps using a real sleep — see
    ``project_abrp_asyncio_sleep_test_patching`` memory for the gotcha.
    """
    assert await async_setup_component(hass, "auth", {})
    assert await async_setup_component(hass, DOMAIN, {})
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.abetterrouteplanner.PREWARM_WINDOW_SECONDS",
        0,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


# ---------------------------------------------------------------------------
# Test 1 – seed-only path
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_seed_only_soc_creates_only_soc_entity(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """JSON seed returns soc only; SSE delivers nothing during pre-warm.

    After setup: ``soc`` entity exists, ``power`` and ``voltage`` do NOT.

    Only metrics that are non-None in the seed + pre-warm data get an
    entity; absent metrics produce no entity at all (no create-then-hide).
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {"soc": {"frac": 0.5}}

    await _lazy_setup(hass, config_entry_with_vehicles)

    assert entity_registry.async_get(SOC_ENTITY_ID) is not None
    assert entity_registry.async_get(POWER_ENTITY_ID) is None
    assert entity_registry.async_get(VOLTAGE_ENTITY_ID) is None


# ---------------------------------------------------------------------------
# Test 2 – pre-warm catches an SSE-only metric
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client")
async def test_prewarm_catches_sse_only_metric(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_sse_client: MagicMock,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """JSON seed empty; SSE delivers a power frame within the pre-warm window.

    After setup: ``power`` entity exists (state ``1234.0``); ``soc`` and
    ``voltage`` do NOT exist.

    The SSE background task runs during
    ``asyncio.sleep(PREWARM_WINDOW_SECONDS)`` and merges the power frame into
    ``coordinator.data`` before the sensor platform inspects it.  In these
    tests the sleep is patched to ``AsyncMock()`` (instant), so the SSE frame
    is delivered post-setup via the dispatcher instead — the observable
    end-state is identical either way. Only metrics present in the seed or
    SSE data get an entity.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}
    mock_sse_client.set_frames([build_telemetry_frame(MOCK_VEHICLE_ID, power=1234.0)])

    await _lazy_setup(hass, config_entry_with_vehicles)

    state = hass.states.get(POWER_ENTITY_ID)
    assert state is not None
    assert state.state == "1234.0"

    assert entity_registry.async_get(SOC_ENTITY_ID) is None
    assert entity_registry.async_get(VOLTAGE_ENTITY_ID) is None


# ---------------------------------------------------------------------------
# Test 3 – post-window dispatcher creates entity on late arrival
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_post_window_dispatcher_creates_entity(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """JSON empty; pre-warm delivers nothing; voltage arrives after setup.

    Sequence:
    1. Setup completes: zero telemetry entities.
    2. SSE delivers ``{voltage: {v: 400}}``.
    3. Exactly one ``voltage`` entity is created (state ``400.0``);
       ``soc`` and ``power`` remain absent.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _lazy_setup(hass, config_entry_with_vehicles)

    assert entity_registry.async_get(SOC_ENTITY_ID) is None
    assert entity_registry.async_get(POWER_ENTITY_ID) is None
    assert entity_registry.async_get(VOLTAGE_ENTITY_ID) is None

    _push_frame(
        config_entry_with_vehicles,
        build_telemetry_frame(MOCK_VEHICLE_ID, voltage=400.0),
    )
    await hass.async_block_till_done()

    assert entity_registry.async_get(VOLTAGE_ENTITY_ID) is not None
    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.state == "400.0"

    assert entity_registry.async_get(SOC_ENTITY_ID) is None
    assert entity_registry.async_get(POWER_ENTITY_ID) is None

    # Voltage lives in the main Sensors bucket — pin via the registry
    # (NOT ``state.attributes``, which never carries the category).
    registry_entry = entity_registry.async_get(VOLTAGE_ENTITY_ID)
    assert registry_entry is not None
    assert registry_entry.entity_category is None


# ---------------------------------------------------------------------------
# Test 4 – soc-time-only-then-frac regression (predicate correctness gate)
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_soc_time_only_then_frac_regression(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """A ``{soc: {time: T}}`` frame must not prematurely create the soc entity.

    Wire shape: ``{vehicleId: ..., soc: {time: 12345}}`` — the ``frac`` inner
    field is absent.  ``_soc_percent`` returns ``None``.

    A *top-level-key* dispatcher (wrong) fires on the first ``soc`` key write,
    sees ``None``, does not create the entity, AND marks ``soc`` as "seen" so
    the subsequent ``{soc: {frac: 0.5}}`` frame never re-dispatches → entity
    permanently invisible.

    The *predicate-based* dispatcher (correct) only fires when
    ``value_fn(merged)`` is non-None.  So:
    * Frame 1 ``{soc: {time: 12345}}`` → soc entity must NOT exist.
    * Frame 2 ``{soc: {frac: 0.5}}``  → soc entity IS created (state ``50.0``).
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _lazy_setup(hass, config_entry_with_vehicles)

    # Frame 1: soc.time only — value_fn returns None → entity must NOT appear
    _push_frame(
        config_entry_with_vehicles,
        {"vehicleId": MOCK_VEHICLE_ID, "soc": {"time": 12345}},
    )
    await hass.async_block_till_done()

    assert entity_registry.async_get(SOC_ENTITY_ID) is None

    # Frame 2: frac arrives — value_fn non-None → dispatcher must create entity
    _push_frame(
        config_entry_with_vehicles,
        build_telemetry_frame(MOCK_VEHICLE_ID, soc=0.5),
    )
    await hass.async_block_till_done()

    assert entity_registry.async_get(SOC_ENTITY_ID) is not None
    state = hass.states.get(SOC_ENTITY_ID)
    assert state is not None
    assert state.state == "50.0"


# ---------------------------------------------------------------------------
# Test 5 – dispatcher idempotency
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_dispatcher_idempotent_on_repeated_frames(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """Two consecutive non-null power frames must create exactly one power entity.

    The ``_presence_seen`` map in the coordinator records the first
    ``(vehicle_id, metric_key)`` dispatch so subsequent non-null frames for
    the same metric are suppressed.  Without this guard each frame would call
    ``async_add_entities``, causing duplicate unique-id warnings and broken
    entity state.

    The pre-frame ``entity_registry.async_get(POWER_ENTITY_ID) is None``
    assertion confirms the entity is created via the dispatcher, not at
    setup.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _lazy_setup(hass, config_entry_with_vehicles)

    # No telemetry entities at setup
    assert entity_registry.async_get(POWER_ENTITY_ID) is None

    _push_frame(
        config_entry_with_vehicles,
        build_telemetry_frame(MOCK_VEHICLE_ID, power=5000.0),
    )
    await hass.async_block_till_done()

    _push_frame(
        config_entry_with_vehicles,
        build_telemetry_frame(MOCK_VEHICLE_ID, power=6000.0),
    )
    await hass.async_block_till_done()

    all_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry_with_vehicles.entry_id
    )
    power_entries = [e for e in all_entries if e.entity_id == POWER_ENTITY_ID]
    assert len(power_entries) == 1

    state = hass.states.get(POWER_ENTITY_ID)
    assert state is not None
    assert state.state == "6000.0"


# ---------------------------------------------------------------------------
# Test 6 – multi-vehicle isolation
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
@pytest.mark.parametrize(
    ("active_vehicle_id", "expected_entity_id", "absent_entity_id"),
    [
        pytest.param(
            MOCK_VEHICLE_ID,
            VOLTAGE_ENTITY_ID,
            VOLTAGE_ENTITY_ID_2,
            id="vehicle_a_active",
        ),
        pytest.param(
            MOCK_VEHICLE_ID_2,
            VOLTAGE_ENTITY_ID_2,
            VOLTAGE_ENTITY_ID,
            id="vehicle_b_active",
        ),
    ],
)
async def test_multi_vehicle_entity_isolation(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
    active_vehicle_id: int,
    expected_entity_id: str,
    absent_entity_id: str,
) -> None:
    """Voltage arriving for vehicle A must not create a voltage entity for vehicle B.

    Uses a two-vehicle config entry (both selected). A voltage frame scoped to
    ``active_vehicle_id`` is pushed; the other vehicle must not receive any
    voltage entity.

    No telemetry entity exists for either vehicle before a frame is pushed;
    the frame scoped to ``active_vehicle_id`` must create one only for that
    vehicle.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SENSOR_TEST_SUB,
        data={
            "auth_implementation": DOMAIN,
            "token": token_entry,
            CONF_VEHICLE_IDS: [str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)],
        },
    )

    await _lazy_setup(hass, entry)

    # No telemetry entities before any frame
    assert entity_registry.async_get(absent_entity_id) is None

    _push_frame(entry, build_telemetry_frame(active_vehicle_id, voltage=400.0))
    await hass.async_block_till_done()

    assert entity_registry.async_get(expected_entity_id) is not None
    assert entity_registry.async_get(absent_entity_id) is None


# ---------------------------------------------------------------------------
# Test 7 – pre-warm timeout discipline (regression guard)
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client")
async def test_prewarm_timeout_setup_completes_with_stuck_sse(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_sse_client: MagicMock,
    mock_seed_responses: AsyncMock,
) -> None:
    """Setup must complete and return True even when the SSE stream never yields.

    Validates that the pre-warm window is a bounded wall-clock cap (not a
    "wait until first frame" gate). If the developer mistakenly awaited the
    first frame, this test would hang against the default stuck-SSE mock.
    Patches ``PREWARM_WINDOW_SECONDS`` to ``0`` so the test asserts the
    structural property (setup returns even with no frames) without paying
    real wall-clock time.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}
    # Default mock_sse_client: blocks forever, never yields any frames.

    assert await async_setup_component(hass, "auth", {})
    assert await async_setup_component(hass, DOMAIN, {})
    config_entry_with_vehicles.add_to_hass(hass)
    with patch(
        "homeassistant.components.abetterrouteplanner.PREWARM_WINDOW_SECONDS",
        0,
    ):
        result = await hass.config_entries.async_setup(
            config_entry_with_vehicles.entry_id
        )
        await hass.async_block_till_done()

    assert result is True
    assert config_entry_with_vehicles.state is ConfigEntryState.LOADED


# ---------------------------------------------------------------------------
# Test 8 – absent-metric entities are never created
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_absent_metric_entities_not_created(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """An empty seed with no SSE frames must produce zero telemetry entities.

    Entities are created only when their metric is actually present in the
    seed or a live frame — there is no create-all-then-hide pattern, so
    absent metrics leave no registry row at all.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _lazy_setup(hass, config_entry_with_vehicles)

    assert entity_registry.async_get(SOC_ENTITY_ID) is None
    assert entity_registry.async_get(POWER_ENTITY_ID) is None
    assert entity_registry.async_get(VOLTAGE_ENTITY_ID) is None


# ---------------------------------------------------------------------------
#  – SoE + odometer sensors (lazy-creation + native/suggested units)
# ---------------------------------------------------------------------------


def _unique_id_lookup(
    entity_registry: er.EntityRegistry, vehicle_id: int, key: str
) -> str | None:
    """Look up an entity_id via ``unique_id`` to decouple from strings.json slugs.

    The new SoE + odometer entities depend on strings.json + a
    ``translations/en.json`` regen the developer hasn't done yet at
    test-write time; finding entities by their planned unique_id shape
    (``f"{entry.unique_id}_{vehicle_id}_{key}"``) avoids hard-coding a
    slug like ``state_of_energy`` that could legitimately change.
    """
    return entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SENSOR_TEST_SUB}_{vehicle_id}_{key}"
    )


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_soe_sensor_lazy_creates_on_first_wh_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """An ``soe.wh`` frame lazy-creates the SoE sensor; native Wh, display kWh.

    Defines the new entity description
    with ``native_unit_of_measurement=UnitOfEnergy.WATT_HOUR`` and
    ``suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR``. HA's
    unit-conversion plumbing renders the state in the suggested unit by
    default; a frame of ``soe.wh = 75000`` therefore shows as ``75.0``.

    Will-fail oracle: without the SENSORS-catalogue entry there is no
    predicate registered for ``soe``, the dispatcher never fires for it,
    and no entity registers.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _lazy_setup(hass, config_entry_with_vehicles)

    assert _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "soe") is None

    _push_frame(
        config_entry_with_vehicles,
        {"vehicleId": MOCK_VEHICLE_ID, "soe": {"wh": 75000.0}},
    )
    await hass.async_block_till_done()

    entity_id = _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "soe")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "75.0"
    assert state.attributes["unit_of_measurement"] == "kWh"
    assert state.attributes["device_class"] == "energy_storage"
    assert state.attributes["state_class"] == "measurement"


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_odometer_sensor_lazy_creates_on_first_m_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """An ``odometer.m`` frame lazy-creates the odometer sensor; native m, display km.

    Defines the odometer description with
    ``native_unit_of_measurement=UnitOfLength.METERS``,
    ``suggested_unit_of_measurement=UnitOfLength.KILOMETERS``,
    ``device_class=SensorDeviceClass.DISTANCE``, and
    ``state_class=SensorStateClass.TOTAL_INCREASING`` (the LTS pipeline
    requirement — odometer is monotonically increasing). The unit
    conversion runs at state-read time (``123456 m → 123.456 km``); the
    ``suggested_display_precision=0`` hint is stored in
    ``entity_registry.options['sensor']`` and applied by the frontend,
    NOT by ``state.state``. Source: ``homeassistant/helpers/entity.py:
    1069-1072`` (``_stringify_state`` uses ``f"{state:.15}"`` — 15 sig
    digits, no precision-hint rounding); precedent at
    ``tests/components/withings/snapshots/test_sensor.ambr``
    (``activity_distance_today`` with ``suggested_display_precision=0``
    snapshots ``state: '1020.121'``).

    Will-fail oracle: same lazy-create shape as the SoE oracle above.
    Also pins ``device_class`` + ``state_class`` so a future refactor
    that flips ``TOTAL_INCREASING`` → ``MEASUREMENT`` (LTS-breaking)
    surfaces as a clean test failure rather than a silent statistics
    drift.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _lazy_setup(hass, config_entry_with_vehicles)

    assert _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "odometer") is None

    _push_frame(
        config_entry_with_vehicles,
        {"vehicleId": MOCK_VEHICLE_ID, "odometer": {"m": 123456.0}},
    )
    await hass.async_block_till_done()

    entity_id = _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "odometer")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "123.456"
    assert float(state.state) == pytest.approx(123.456)
    assert state.attributes["unit_of_measurement"] == "km"
    assert state.attributes["device_class"] == "distance"
    assert state.attributes["state_class"] == "total_increasing"


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
@pytest.mark.parametrize(
    ("metric_key", "frame"),
    [
        pytest.param(
            "soe",
            {"vehicleId": MOCK_VEHICLE_ID, "soe": {"time": 1}},
            id="soe_time_only",
        ),
        pytest.param(
            "soe",
            {"vehicleId": MOCK_VEHICLE_ID, "soe": {"wh": "broken"}},
            id="soe_wh_string",
        ),
        pytest.param(
            "soe",
            {"vehicleId": MOCK_VEHICLE_ID, "soe": {"wh": True}},
            id="soe_wh_bool",
        ),
        pytest.param(
            "odometer",
            {"vehicleId": MOCK_VEHICLE_ID, "odometer": {"time": 1}},
            id="odometer_time_only",
        ),
        pytest.param(
            "odometer",
            {"vehicleId": MOCK_VEHICLE_ID, "odometer": {"m": "broken"}},
            id="odometer_m_string",
        ),
        pytest.param(
            "odometer",
            {"vehicleId": MOCK_VEHICLE_ID, "odometer": {"m": True}},
            id="odometer_m_bool",
        ),
    ],
)
async def test_invalid_soe_or_odometer_frame_does_not_create(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
    metric_key: str,
    frame: dict[str, Any],
) -> None:
    """Predicate-rejected SoE/odometer frames must NOT lazy-create the entity.

    Mirrors the ``test_soc_time_only_then_frac_regression`` shape for
    the new metrics. Catches the same class — bool-isinstance trap
    (``bool ⊂ int``), type-cast misses, inner-time-only partials.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _lazy_setup(hass, config_entry_with_vehicles)

    _push_frame(config_entry_with_vehicles, frame)
    await hass.async_block_till_done()

    assert _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, metric_key) is None


# ---------------------------------------------------------------------------
#  – Ref Consumption (LTS) + Battery Capacity (DIAGNOSTIC/STATIC) +
#            State of Health (LTS) sensors
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_calibrated_ref_cons_sensor_lazy_creates_on_first_wh_per_km_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """A ``calibratedRefCons.wh_per_km`` frame lazy-creates the ref-consumption sensor.

    Defines the description with
    ``native_unit_of_measurement=UnitOfEnergyDistance.WATT_HOUR_PER_KM``,
    ``device_class=SensorDeviceClass.ENERGY_DISTANCE``, and
    ``state_class=SensorStateClass.MEASUREMENT`` (LTS-tracked drift —
    user can graph reference-consumption shifts over time as the
    vehicle's calibration recalibrates).

    No ``suggested_unit_of_measurement`` : HA core's
    locale-driven default (``KM_PER_KILO_WATT_HOUR`` per
    ``sensor/const.py:763``) applies only when the user has selected a
    regional preference. Default test environment has no preference →
    the entity displays the native ``Wh/km`` unit and ``state.state``
    is the raw value.

    Will-fail oracle: without the SENSORS-catalogue entry there is no
    predicate registered for ``calibrated_ref_cons``, the dispatcher
    never fires for it, and no entity registers.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _lazy_setup(hass, config_entry_with_vehicles)

    assert (
        _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "calibrated_ref_cons")
        is None
    )

    _push_frame(
        config_entry_with_vehicles,
        {"vehicleId": MOCK_VEHICLE_ID, "calibratedRefCons": {"wh_per_km": 175.0}},
    )
    await hass.async_block_till_done()

    entity_id = _unique_id_lookup(
        entity_registry, MOCK_VEHICLE_ID, "calibrated_ref_cons"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == pytest.approx(175.0)
    assert state.attributes["unit_of_measurement"] == "Wh/km"
    assert state.attributes["device_class"] == "energy_distance"
    assert state.attributes["state_class"] == "measurement"

    # calibrated_ref_cons lives in the main Sensors bucket.
    registry_entry = entity_registry.async_get(entity_id)
    assert registry_entry is not None
    assert registry_entry.entity_category is None


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_battery_capacity_sensor_lazy_creates_static(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """A ``batteryCapacity.wh`` frame lazy-creates the capacity sensor as STATIC.

    Defines the description with
    ``native_unit_of_measurement=UnitOfEnergy.WATT_HOUR``,
    ``suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR``,
    ``device_class=SensorDeviceClass.ENERGY_STORAGE``,
    and crucially **NO ``state_class``** — capacity is a static
    nameplate value, not a measurement, so opting out of the LTS
    pipeline prevents the recorder from emitting per-poll history for
    a value that effectively never changes.

    Will-fail oracle. The
    ``"state_class" not in state.attributes`` assertion catches a
    future regression where someone reflexively adds
    ``MEASUREMENT`` because they're inheriting the odometer template.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _lazy_setup(hass, config_entry_with_vehicles)

    assert (
        _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "battery_capacity") is None
    )

    _push_frame(
        config_entry_with_vehicles,
        {"vehicleId": MOCK_VEHICLE_ID, "batteryCapacity": {"wh": 75000.0}},
    )
    await hass.async_block_till_done()

    entity_id = _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "battery_capacity")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "75.0"
    assert state.attributes["unit_of_measurement"] == "kWh"
    assert state.attributes["device_class"] == "energy_storage"
    assert "state_class" not in state.attributes, (
        "battery_capacity is STATIC; state_class must be absent (LTS opt-out)"
    )

    # battery_capacity lives in the main Sensors bucket.
    registry_entry = entity_registry.async_get(entity_id)
    assert registry_entry is not None
    assert registry_entry.entity_category is None


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_soh_sensor_lazy_creates_on_first_frac_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """A ``soh.frac`` frame lazy-creates the State-of-Health sensor (`frac × 100` %).

    Defines the description with
    ``state_class=SensorStateClass.MEASUREMENT`` (LTS-tracked drift —
    battery health degrades slowly over years; LTS captures it),
    ``native_unit_of_measurement=PERCENTAGE``, and **NO
    ``device_class``** (per plan: ``SensorDeviceClass.BATTERY``'s
    docstring is "Percentage of battery that is left" — that's SoC,
    not SoH; mis-classifying SoH as ``BATTERY`` would confuse the
    energy dashboard).

    Value semantic : higher = healthier. ``frac=0.92 →
    92 %``. Industry-standard SoH convention. The
    ``"device_class" not in state.attributes`` assertion pins this
    deliberate omission.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _lazy_setup(hass, config_entry_with_vehicles)

    assert _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "soh") is None

    _push_frame(
        config_entry_with_vehicles,
        {"vehicleId": MOCK_VEHICLE_ID, "soh": {"frac": 0.92}},
    )
    await hass.async_block_till_done()

    entity_id = _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "soh")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "92.0"
    assert state.attributes["unit_of_measurement"] == "%"
    assert state.attributes["state_class"] == "measurement"
    assert "device_class" not in state.attributes, (
        "SoH is not SensorDeviceClass.BATTERY (that's SoC); device_class must be absent"
    )

    # SoH lives in the main Sensors bucket.
    registry_entry = entity_registry.async_get(entity_id)
    assert registry_entry is not None
    assert registry_entry.entity_category is None


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_battery_temperature_sensor_stays_primary_category(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """Battery Temperature stays primary (``entity_category is None``).

    Battery Temperature is the canonical preconditioning trigger
    (Renault precedent at ``homeassistant/components/renault/sensor.py:221``)
    and stays primary. This is the negative pin: catches a future
    reflexive copy-paste flip that would move battery_temperature
    into the diagnostic bucket.

    A regression that adds ``entity_category=EntityCategory.DIAGNOSTIC``
    to the battery_temperature description fails this test loudly.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _lazy_setup(hass, config_entry_with_vehicles)

    assert (
        _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "battery_temperature")
        is None
    )

    _push_frame(
        config_entry_with_vehicles,
        {"vehicleId": MOCK_VEHICLE_ID, "batteryTemperature": {"c": 22.5}},
    )
    await hass.async_block_till_done()

    entity_id = _unique_id_lookup(
        entity_registry, MOCK_VEHICLE_ID, "battery_temperature"
    )
    assert entity_id is not None
    registry_entry = entity_registry.async_get(entity_id)
    assert registry_entry is not None
    assert registry_entry.entity_category is None, (
        "battery_temperature is the canonical preconditioning trigger; "
        "it must stay primary (no entity_category)"
    )


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
@pytest.mark.parametrize(
    ("metric_key", "frame"),
    [
        # calibrated_ref_cons negation oracles
        pytest.param(
            "calibrated_ref_cons",
            {"vehicleId": MOCK_VEHICLE_ID, "calibratedRefCons": {"time": 1}},
            id="ref_cons_time_only",
        ),
        pytest.param(
            "calibrated_ref_cons",
            {
                "vehicleId": MOCK_VEHICLE_ID,
                "calibratedRefCons": {"wh_per_km": "high"},
            },
            id="ref_cons_string",
        ),
        pytest.param(
            "calibrated_ref_cons",
            {"vehicleId": MOCK_VEHICLE_ID, "calibratedRefCons": {"wh_per_km": True}},
            id="ref_cons_bool",
        ),
        # battery_capacity negation oracles
        pytest.param(
            "battery_capacity",
            {"vehicleId": MOCK_VEHICLE_ID, "batteryCapacity": {"time": 1}},
            id="capacity_time_only",
        ),
        pytest.param(
            "battery_capacity",
            {"vehicleId": MOCK_VEHICLE_ID, "batteryCapacity": {"wh": "huge"}},
            id="capacity_string",
        ),
        pytest.param(
            "battery_capacity",
            {"vehicleId": MOCK_VEHICLE_ID, "batteryCapacity": {"wh": True}},
            id="capacity_bool",
        ),
        # soh negation oracles
        pytest.param(
            "soh",
            {"vehicleId": MOCK_VEHICLE_ID, "soh": {"time": 1}},
            id="soh_time_only",
        ),
        pytest.param(
            "soh",
            {"vehicleId": MOCK_VEHICLE_ID, "soh": {"frac": "healthy"}},
            id="soh_frac_string",
        ),
        pytest.param(
            "soh",
            {"vehicleId": MOCK_VEHICLE_ID, "soh": {"frac": True}},
            id="soh_frac_bool",
        ),
    ],
)
async def test_invalid_ref_cons_capacity_or_soh_frame_does_not_create(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
    metric_key: str,
    frame: dict[str, Any],
) -> None:
    """Predicate-rejected metric frames must NOT lazy-create the entity.

    Mirrors the SoE/odometer presence-trap test for the three new
    metrics. Covers the same
    failure class — bool-isinstance trap (``bool ⊂ int`` in Python so
    ``isinstance(True, (int, float))`` is True; the explicit
    ``isinstance(x, bool)`` exclude is what saves us), string-cast
    misses, and inner-time-only partials.

    Adversarial-input enumeration — each new
    sensor's empty/null/{}/string/bool shape is exercised.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _lazy_setup(hass, config_entry_with_vehicles)

    _push_frame(config_entry_with_vehicles, frame)
    await hass.async_block_till_done()

    assert _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, metric_key) is None


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_soh_frac_overshoot_above_1_surfaces_above_100_percent(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """A ``soh.frac > 1.0`` post-recalibration overshoot surfaces uncapped (>100%).

    Adversarial-input row for SoH: "``frac > 1.0``
    (post-recalibration overshoot) → SoH > 100%. HA frontend tolerates;
    surfaces with ``%`` unit. Not range-clamped — consistent with how
    ``soc`` doesn't clamp."

    Regression pin: catches a future regression where someone
    reflexively adds ``min(frac * 100, 100.0)`` to the value_fn,
    flattening the post-recalibration drift signal LTS is meant to
    capture.

    Will-fail oracle today (no impl); flips a hypothetical
    clamp-to-100 impl tomorrow.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _lazy_setup(hass, config_entry_with_vehicles)

    _push_frame(
        config_entry_with_vehicles,
        {"vehicleId": MOCK_VEHICLE_ID, "soh": {"frac": 1.05}},
    )
    await hass.async_block_till_done()

    entity_id = _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "soh")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == pytest.approx(105.0)


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_battery_capacity_recalibration_jump_updates_state(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """A capacity recalibration jump is reflected in ``state.state``.

    Documents capacity as
    "provisional STATIC" — if post-deploy field reports show daily
    drift > 1% the follow-up flips state_class to MEASUREMENT. This
    test pins the contract that the STATIC framing does NOT prevent
    state updates: a second frame with a different ``batteryCapacity.wh``
    must surface cleanly (no exception, value updates).

    The LTS opt-out (no state_class) means the recorder skips this
    entity; the user sees the change as a single state transition in
    the device card, not a long-term graph. That's the deliberate UX
    today — the test pins it so a future flip to MEASUREMENT is a
    code-review conversation, not a silent recorder regression.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _lazy_setup(hass, config_entry_with_vehicles)

    _push_frame(
        config_entry_with_vehicles,
        {"vehicleId": MOCK_VEHICLE_ID, "batteryCapacity": {"wh": 75000.0}},
    )
    await hass.async_block_till_done()

    entity_id = _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "battery_capacity")
    assert entity_id is not None
    first_state = hass.states.get(entity_id)
    assert first_state is not None
    assert first_state.state == "75.0"

    _push_frame(
        config_entry_with_vehicles,
        {"vehicleId": MOCK_VEHICLE_ID, "batteryCapacity": {"wh": 74500.0}},
    )
    await hass.async_block_till_done()

    second_state = hass.states.get(entity_id)
    assert second_state is not None
    assert second_state.state == "74.5"


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_new_sensor_multi_vehicle_isolation(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """A metric frame for vehicle A must not create the entity on vehicle B.

    Existing dispatcher infrastructure covers the
    framework path (per-vehicle predicate evaluation), but a re-pin
    against the three new keys catches any future refactor that
    accidentally collapses the per-vehicle predicate map for one of
    the new metrics.

    Two vehicles selected; only vehicle A receives a
    ``calibratedRefCons`` frame. Vehicle B remains without a
    ref-consumption entity even though both are selected and in
    the garage.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SENSOR_TEST_SUB,
        data={
            "auth_implementation": DOMAIN,
            "token": token_entry,
            CONF_VEHICLE_IDS: [str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)],
        },
    )
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}
    mock_seed_responses.responses[MOCK_VEHICLE_ID_2] = {}

    await _lazy_setup(hass, entry)

    _push_frame(
        entry,
        {
            "vehicleId": MOCK_VEHICLE_ID,
            "calibratedRefCons": {"wh_per_km": 175.0},
        },
    )
    await hass.async_block_till_done()

    assert (
        _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "calibrated_ref_cons")
        is not None
    )
    assert (
        _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID_2, "calibrated_ref_cons")
        is None
    )
