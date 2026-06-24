"""Tests for lazy / dispatcher entity creation on the aioabrp telemetry driver.

Telemetry state is now typed: the coordinator holds
``dict[int, dict[Metric, MetricValue]]`` and the library
(:class:`aioabrp.TelemetryStream`) owns wire parsing, reconnect, merge and
monotonicity. These tests cover only the HA-side lazy-creation contract:

* a metric present in the seed snapshot creates its entity at platform-forward
  time;
* a metric absent from the seed creates its entity only when a later stream
  frame first carries a non-None value (via the ``signal_new_metric``
  dispatcher);
* absent metrics leave no registry row at all (no create-then-hide);
* per-vehicle isolation, idempotency, unit / device-class / state-class /
  entity-category surfacing.

Wire-level rejection (bool / string / inner-time-only partials) and frame
merge / monotonicity now live in the aioabrp library, which only ever emits a
typed ``MetricValue`` for a genuinely-present metric — those concerns are
covered by the library's own tests, not here.

The seed path is driven by ``mock_abrp_client.seed_responses``; the stream path
is driven by ``fake_stream.fire_frame`` (a synchronous double for the real
``TelemetryStream``).
"""

from typing import Any
from unittest.mock import AsyncMock

from aioabrp import Telemetry
import pytest

from homeassistant.components.abetterrouteplanner.const import CONF_VEHICLE_IDS, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import (
    MOCK_VEHICLE_ID,
    MOCK_VEHICLE_ID_2,
    SENSOR_TEST_SUB,
    build_metric_value,
)

from tests.common import MockConfigEntry

# Entity IDs for vehicle 1 (Rivian R2 2027 Standard Long Range)
SOC_ENTITY_ID = "sensor.rivian_r2_2027_standard_long_range_soc"
POWER_ENTITY_ID = "sensor.rivian_r2_2027_standard_long_range_power"
VOLTAGE_ENTITY_ID = "sensor.rivian_r2_2027_standard_long_range_voltage"

# Entity IDs for vehicle 2 (Rivian R1S 2024 Quad Max)
VOLTAGE_ENTITY_ID_2 = "sensor.rivian_r1s_2024_quad_max_voltage"


async def _lazy_setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the integration with the synchronous ``fake_stream`` double.

    The ``fake_stream`` fixture patches ``TelemetryStream`` with a synchronous
    double, so setup returns immediately without a real SSE consumer.
    """
    assert await async_setup_component(hass, "auth", {})
    assert await async_setup_component(hass, DOMAIN, {})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _unique_id_lookup(
    entity_registry: er.EntityRegistry, vehicle_id: int, key: str
) -> str | None:
    """Look up an entity_id via ``unique_id`` to decouple from strings.json slugs.

    Finds entities by their unique_id shape
    (``f"{entry.unique_id}_{vehicle_id}_{key}"``) so the assertions don't
    hard-code translation slugs that could legitimately change.
    """
    return entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SENSOR_TEST_SUB}_{vehicle_id}_{key}"
    )


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_seed_only_soc_creates_only_soc_entity(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
) -> None:
    """The seed returns soc only; the stream delivers nothing.

    After setup: the ``soc`` entity exists, ``power`` and ``voltage`` do NOT.

    Only metrics that are non-None in the seed snapshot get an entity at
    platform-forward time; absent metrics produce no entity at all (no
    create-then-hide).
    """
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = Telemetry(
        soc=build_metric_value(50.0)
    )

    await _lazy_setup(hass, config_entry_with_vehicles)

    assert entity_registry.async_get(SOC_ENTITY_ID) is not None
    assert entity_registry.async_get(POWER_ENTITY_ID) is None
    assert entity_registry.async_get(VOLTAGE_ENTITY_ID) is None


@pytest.mark.usefixtures("mock_abrp_client")
async def test_stream_only_metric_creates_entity(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """The seed is empty; a power frame arrives over the stream.

    After firing: the ``power`` entity exists (state ``1234.0``); ``soc`` and
    ``voltage`` do NOT exist. Only metrics present in the seed or a live frame
    get an entity.
    """
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = Telemetry()

    await _lazy_setup(hass, config_entry_with_vehicles)

    assert entity_registry.async_get(POWER_ENTITY_ID) is None

    fake_stream.fire_frame(MOCK_VEHICLE_ID, Telemetry(power=build_metric_value(1234.0)))
    await hass.async_block_till_done()

    state = hass.states.get(POWER_ENTITY_ID)
    assert state is not None
    assert state.state == "1234.0"

    assert entity_registry.async_get(SOC_ENTITY_ID) is None
    assert entity_registry.async_get(VOLTAGE_ENTITY_ID) is None


@pytest.mark.usefixtures("mock_abrp_client")
async def test_post_setup_dispatcher_creates_entity(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """The seed is empty; voltage arrives only after setup completes.

    Sequence:
    1. Setup completes: zero telemetry entities.
    2. The stream delivers a voltage frame.
    3. Exactly one ``voltage`` entity is created (state ``400.0``); ``soc`` and
       ``power`` remain absent. Voltage lives in the main Sensors bucket
       (``entity_category is None``).
    """
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = Telemetry()

    await _lazy_setup(hass, config_entry_with_vehicles)

    assert entity_registry.async_get(SOC_ENTITY_ID) is None
    assert entity_registry.async_get(POWER_ENTITY_ID) is None
    assert entity_registry.async_get(VOLTAGE_ENTITY_ID) is None

    fake_stream.fire_frame(
        MOCK_VEHICLE_ID, Telemetry(voltage=build_metric_value(400.0))
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


@pytest.mark.usefixtures("mock_abrp_client")
async def test_dispatcher_idempotent_on_repeated_frames(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """Two consecutive non-null power frames must create exactly one power entity.

    The ``_presence_seen`` map in the coordinator records the first
    ``(vehicle_id, metric)`` dispatch so subsequent non-null frames for the
    same metric are suppressed. Without this guard each frame would call
    ``async_add_entities``, causing duplicate unique-id warnings and broken
    entity state. The second frame's value still surfaces as the new state.
    """
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = Telemetry()

    await _lazy_setup(hass, config_entry_with_vehicles)

    # No telemetry entities at setup.
    assert entity_registry.async_get(POWER_ENTITY_ID) is None

    fake_stream.fire_frame(MOCK_VEHICLE_ID, Telemetry(power=build_metric_value(5000.0)))
    await hass.async_block_till_done()

    fake_stream.fire_frame(MOCK_VEHICLE_ID, Telemetry(power=build_metric_value(6000.0)))
    await hass.async_block_till_done()

    all_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry_with_vehicles.entry_id
    )
    power_entries = [e for e in all_entries if e.entity_id == POWER_ENTITY_ID]
    assert len(power_entries) == 1

    state = hass.states.get(POWER_ENTITY_ID)
    assert state is not None
    assert state.state == "6000.0"


@pytest.mark.usefixtures("mock_abrp_client")
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
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
    active_vehicle_id: int,
    expected_entity_id: str,
    absent_entity_id: str,
) -> None:
    """Voltage arriving for vehicle A must not create a voltage entity for vehicle B.

    Uses a two-vehicle config entry (both selected). A voltage frame scoped to
    ``active_vehicle_id`` is fired; the other vehicle must not receive any
    voltage entity. No telemetry entity exists for either vehicle before a
    frame is fired.
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
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = Telemetry()
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID_2] = Telemetry()

    await _lazy_setup(hass, entry)

    # No telemetry entities before any frame.
    assert entity_registry.async_get(absent_entity_id) is None

    fake_stream.fire_frame(
        active_vehicle_id, Telemetry(voltage=build_metric_value(400.0))
    )
    await hass.async_block_till_done()

    assert entity_registry.async_get(expected_entity_id) is not None
    assert entity_registry.async_get(absent_entity_id) is None


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_absent_metric_entities_not_created(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
) -> None:
    """An empty seed with no stream frames must produce zero telemetry entities.

    Entities are created only when their metric is actually present in the
    seed or a live frame — there is no create-all-then-hide pattern, so absent
    metrics leave no registry row at all.
    """
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = Telemetry()

    await _lazy_setup(hass, config_entry_with_vehicles)

    assert entity_registry.async_get(SOC_ENTITY_ID) is None
    assert entity_registry.async_get(POWER_ENTITY_ID) is None
    assert entity_registry.async_get(VOLTAGE_ENTITY_ID) is None


@pytest.mark.usefixtures("mock_abrp_client")
async def test_soe_sensor_lazy_creates_on_first_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """An ``soe`` frame lazy-creates the SoE sensor; native Wh, display kWh.

    The description sets ``native_unit_of_measurement=WATT_HOUR`` and
    ``suggested_unit_of_measurement=KILO_WATT_HOUR``; HA's unit conversion
    renders the state in the suggested unit, so a ``MetricValue`` of
    ``75000`` Wh shows as ``75.0`` kWh.
    """
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = Telemetry()

    await _lazy_setup(hass, config_entry_with_vehicles)

    assert _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "soe") is None

    fake_stream.fire_frame(MOCK_VEHICLE_ID, Telemetry(soe=build_metric_value(75000.0)))
    await hass.async_block_till_done()

    entity_id = _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "soe")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "75.0"
    assert state.attributes["unit_of_measurement"] == "kWh"
    assert state.attributes["device_class"] == "energy_storage"
    assert state.attributes["state_class"] == "measurement"


@pytest.mark.usefixtures("mock_abrp_client")
async def test_odometer_sensor_lazy_creates_on_first_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """An ``odometer`` frame lazy-creates the odometer sensor; native m, display km.

    The description sets ``native_unit_of_measurement=METERS``,
    ``suggested_unit_of_measurement=KILOMETERS``,
    ``device_class=DISTANCE``, and ``state_class=TOTAL_INCREASING`` (the LTS
    requirement — odometer is monotonically increasing). Unit conversion runs
    at state-read time (``123456 m → 123.456 km``); the
    ``suggested_display_precision=0`` hint is stored in the registry options
    and applied by the frontend, not by ``state.state``.

    Pins ``device_class`` + ``state_class`` so a future refactor that flips
    ``TOTAL_INCREASING`` → ``MEASUREMENT`` (LTS-breaking) surfaces as a clean
    test failure rather than a silent statistics drift.
    """
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = Telemetry()

    await _lazy_setup(hass, config_entry_with_vehicles)

    assert _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "odometer") is None

    fake_stream.fire_frame(
        MOCK_VEHICLE_ID, Telemetry(odometer=build_metric_value(123456.0))
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


@pytest.mark.usefixtures("mock_abrp_client")
async def test_calibrated_ref_cons_sensor_lazy_creates_on_first_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """A ``calibrated_ref_cons`` frame lazy-creates the ref-consumption sensor.

    The description sets ``native_unit_of_measurement=WATT_HOUR_PER_KM``,
    ``device_class=ENERGY_DISTANCE``, and ``state_class=MEASUREMENT``
    (LTS-tracked drift). No ``suggested_unit_of_measurement`` — the default
    test environment has no regional preference, so the entity displays the
    native ``Wh/km`` unit and ``state.state`` is the raw value. Lives in the
    main Sensors bucket (``entity_category is None``).
    """
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = Telemetry()

    await _lazy_setup(hass, config_entry_with_vehicles)

    assert (
        _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "calibrated_ref_cons")
        is None
    )

    fake_stream.fire_frame(
        MOCK_VEHICLE_ID, Telemetry(calibrated_ref_cons=build_metric_value(175.0))
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


@pytest.mark.usefixtures("mock_abrp_client")
async def test_battery_capacity_sensor_lazy_creates_static(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """A ``battery_capacity`` frame lazy-creates the capacity sensor as STATIC.

    The description sets ``native_unit_of_measurement=WATT_HOUR``,
    ``suggested_unit_of_measurement=KILO_WATT_HOUR``,
    ``device_class=ENERGY_STORAGE``, and crucially **NO ``state_class``** —
    capacity is a static nameplate value, so opting out of the LTS pipeline
    prevents the recorder from emitting per-poll history. The
    ``"state_class" not in state.attributes`` assertion catches a future
    regression where someone reflexively adds ``MEASUREMENT``.
    """
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = Telemetry()

    await _lazy_setup(hass, config_entry_with_vehicles)

    assert (
        _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "battery_capacity") is None
    )

    fake_stream.fire_frame(
        MOCK_VEHICLE_ID, Telemetry(battery_capacity=build_metric_value(75000.0))
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


@pytest.mark.usefixtures("mock_abrp_client")
async def test_soh_sensor_lazy_creates_on_first_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """A ``soh`` frame lazy-creates the State-of-Health sensor (percent).

    The description sets ``state_class=MEASUREMENT`` (LTS-tracked degradation),
    ``native_unit_of_measurement=PERCENTAGE``, and **NO ``device_class``**
    (``SensorDeviceClass.BATTERY`` means SoC, not SoH; mis-classifying SoH as
    BATTERY would confuse the energy dashboard). SoH is already in percent in
    the ``MetricValue`` (the library did the x100), so ``92.0`` -> ``92.0 %``.
    The ``"device_class" not in state.attributes`` assertion pins the omission.
    """
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = Telemetry()

    await _lazy_setup(hass, config_entry_with_vehicles)

    assert _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "soh") is None

    fake_stream.fire_frame(MOCK_VEHICLE_ID, Telemetry(soh=build_metric_value(92.0)))
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


@pytest.mark.usefixtures("mock_abrp_client")
async def test_battery_temperature_sensor_stays_primary_category(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """Battery Temperature stays primary (``entity_category is None``).

    Battery Temperature is the canonical preconditioning trigger and stays
    primary. This is the negative pin: a regression that adds
    ``entity_category=EntityCategory.DIAGNOSTIC`` to the description fails this
    test loudly.
    """
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = Telemetry()

    await _lazy_setup(hass, config_entry_with_vehicles)

    assert (
        _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "battery_temperature")
        is None
    )

    fake_stream.fire_frame(
        MOCK_VEHICLE_ID, Telemetry(battery_temperature=build_metric_value(22.5))
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


@pytest.mark.usefixtures("mock_abrp_client")
async def test_soh_above_100_percent_surfaces_uncapped(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """A post-recalibration SoH overshoot (> 100%) surfaces uncapped.

    SoH is already in percent in the ``MetricValue``; a value of ``105.0``
    surfaces as ``105.0`` — not range-clamped, consistent with how ``soc``
    doesn't clamp. Regression pin: catches a future ``min(value, 100.0)`` that
    would flatten the post-recalibration drift signal LTS is meant to capture.
    """
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = Telemetry()

    await _lazy_setup(hass, config_entry_with_vehicles)

    fake_stream.fire_frame(MOCK_VEHICLE_ID, Telemetry(soh=build_metric_value(105.0)))
    await hass.async_block_till_done()

    entity_id = _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "soh")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == pytest.approx(105.0)


@pytest.mark.usefixtures("mock_abrp_client")
async def test_battery_capacity_recalibration_jump_updates_state(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """A capacity recalibration jump is reflected in ``state.state``.

    The STATIC framing (no ``state_class``) must NOT prevent state updates: a
    second frame with a different ``battery_capacity`` value surfaces cleanly
    (no exception, value updates). The LTS opt-out means the recorder skips
    this entity, so the user sees the change as a single state transition.
    """
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = Telemetry()

    await _lazy_setup(hass, config_entry_with_vehicles)

    fake_stream.fire_frame(
        MOCK_VEHICLE_ID, Telemetry(battery_capacity=build_metric_value(75000.0))
    )
    await hass.async_block_till_done()

    entity_id = _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "battery_capacity")
    assert entity_id is not None
    first_state = hass.states.get(entity_id)
    assert first_state is not None
    assert first_state.state == "75.0"

    fake_stream.fire_frame(
        MOCK_VEHICLE_ID, Telemetry(battery_capacity=build_metric_value(74500.0))
    )
    await hass.async_block_till_done()

    second_state = hass.states.get(entity_id)
    assert second_state is not None
    assert second_state.state == "74.5"


@pytest.mark.usefixtures("mock_abrp_client")
async def test_new_sensor_multi_vehicle_isolation(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """A metric frame for vehicle A must not create the entity on vehicle B.

    Two vehicles selected; only vehicle A receives a ``calibrated_ref_cons``
    frame. Vehicle B remains without a ref-consumption entity even though both
    are selected and in the garage — a re-pin against the new keys catches any
    future refactor that collapses the per-vehicle predicate map.
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
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = Telemetry()
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID_2] = Telemetry()

    await _lazy_setup(hass, entry)

    fake_stream.fire_frame(
        MOCK_VEHICLE_ID, Telemetry(calibrated_ref_cons=build_metric_value(175.0))
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
