"""Tests for the A Better Routeplanner sensor platform.

Surface under test:

* One HA device per ``vehicle_id`` in ``entry.data[CONF_VEHICLE_IDS]``,
  anchored at integration setup with full DeviceInfo metadata.
* Lazily-created telemetry sensors per device.
* Filter is applied at ``async_setup_entry`` time: vehicles not in
  ``CONF_VEHICLE_IDS`` are dropped silently; selected ``vehicle_id`` values
  missing from the coordinator payload log a warning and skip (no
  entity, no device, no repair issue).
"""

from collections.abc import Callable, Generator
from datetime import UTC, datetime
import json
import logging
from pathlib import Path
from typing import Any, get_args
from unittest.mock import AsyncMock, patch

from freezegun import freeze_time
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import abetterrouteplanner as abrp_module
from homeassistant.components.abetterrouteplanner import AbrpData
from homeassistant.components.abetterrouteplanner._sensor_value_fns import (
    _CHARGING_STATE_OPTIONS,
    _charging_state,
    _power_w,
    _soc_percent,
    _unknown_charging_states_seen,
    _voltage_v,
)
from homeassistant.components.abetterrouteplanner._telemetry_models import (
    ChargingStateValue,
)
from homeassistant.components.abetterrouteplanner.api import AbrpVehicle, CatalogEntry
from homeassistant.components.abetterrouteplanner.const import CONF_VEHICLE_IDS, DOMAIN
from homeassistant.components.abetterrouteplanner.sensor import SENSORS_BY_KEY
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import (
    MOCK_VEHICLE_ID,
    MOCK_VEHICLE_ID_2,
    MOCK_VEHICLE_MODEL,
    SENSOR_TEST_SUB,
    build_telemetry_frame,
)

from tests.common import (
    MockConfigEntry,
    mock_restore_cache_with_extra_data,
    snapshot_platform,
)

SOC_ENTITY_ID = "sensor.rivian_r2_2027_standard_long_range_soc"
POWER_ENTITY_ID = "sensor.rivian_r2_2027_standard_long_range_power"
VOLTAGE_ENTITY_ID = "sensor.rivian_r2_2027_standard_long_range_voltage"
CHARGING_STATE_ENTITY_ID = "sensor.rivian_r2_2027_standard_long_range_charging_state"
CHARGING_STATE_UNIQUE_ID = f"{SENSOR_TEST_SUB}_{MOCK_VEHICLE_ID}_charging_state"

# Integration package dir — the cross-pin guard reads the source
# ``strings.json`` / ``icons.json`` (not the generated ``translations/en.json``)
# so a missing label or icon for a charging-state option fails loudly.
_INTEGRATION_DIR = Path(abrp_module.__file__).parent


@pytest.fixture(autouse=True)
def _isolate_unknown_charging_states() -> Generator[None]:
    """Keep the module-level ``_unknown_charging_states_seen`` set test-local.

    ``_charging_state`` records every unrecognized wire member in a
    process-global set to dedup its once-per-process WARNING. Several tests
    here feed it unrecognized members (``"FOO"`` in the null-safety
    parametrize, ``"WARP_DRIVE"`` in the warn-once test); without isolation
    those leak across tests and make the warn-once dedup assertion
    order-dependent. Snapshot the set before each test and restore it after
    so no test pollutes the global.
    """
    snapshot = set(_unknown_charging_states_seen)
    yield
    _unknown_charging_states_seen.clear()
    _unknown_charging_states_seen.update(snapshot)


async def _setup_integration(
    hass: HomeAssistant, entry: MockConfigEntry
) -> MockConfigEntry:
    """Register the integration's OAuth implementation and set up the entry.

    Patches the SSE pre-warm constant to ``0`` so tests neither pay the
    wall-clock cost nor deadlock under freezegun's monotonic patch.
    Patching the constant (rather than module-globally mocking
    ``asyncio.sleep``) keeps the SSE retry backoff loop using a real
    sleep — see ``project_abrp_asyncio_sleep_test_patching`` memory.
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
    return entry


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_abrp_client", "mock_sse_client"
)
async def test_unselected_vehicle_absent_from_registries(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Unselected vehicles never appear in device or entity registries.

    Only the first vehicle is in ``CONF_VEHICLE_IDS``; the second vehicle must
    not surface as a device, and no entity must carry its ``vehicle_id``
    in its unique_id. The selected vehicle's device anchor is verified by
    :func:`test_per_vehicle_device_anchored_at_setup`; this test isolates
    the filter behaviour for the unselected case.
    """
    await _setup_integration(hass, config_entry_with_vehicles)

    # Device identifiers and entity unique_ids are scoped by
    # ``entry.unique_id`` (the JWT ``sub``) so two ABRP accounts on the same
    # HA can't collide on a shared ``vehicle_id``. Read the sub off the
    # fixture rather than the bare constant so the assertion stays correct
    # if the fixture's unique_id is ever parametrized.
    scope = config_entry_with_vehicles.unique_id
    selected_device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{scope}_{MOCK_VEHICLE_ID}")}
    )
    assert selected_device is not None

    unselected_device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{scope}_{MOCK_VEHICLE_ID_2}")}
    )
    assert unselected_device is None

    unselected_marker = f"_{MOCK_VEHICLE_ID_2}_"
    for registry_entry in er.async_entries_for_config_entry(
        entity_registry, config_entry_with_vehicles.entry_id
    ):
        assert unselected_marker not in registry_entry.unique_id


@pytest.mark.usefixtures("mock_abrp_client")
async def test_selected_vehicle_missing_from_garage_logs_and_skips(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A selected ``vehicle_id`` missing from the garage emits nothing + warns.

    Mirrors the user-visible behaviour when a vehicle was removed from
    the ABRP account between picker submission and the first coordinator
    refresh: no entity, no device, no repair — just a log line.
    """
    bogus_id = "99999999"
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SENSOR_TEST_SUB,
        data={
            "auth_implementation": DOMAIN,
            "token": token_entry,
            CONF_VEHICLE_IDS: [bogus_id],
        },
    )

    with caplog.at_level(
        logging.WARNING, logger="homeassistant.components.abetterrouteplanner"
    ):
        await _setup_integration(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    assert not er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert not dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    assert bogus_id in caplog.text


# Telemetry sensor tests ------------------------------------------------------


def _push_telemetry_frame(entry: MockConfigEntry, frame: dict[str, Any]) -> None:
    """Push a synthesized frame into the telemetry coordinator's apply_frame.

    Tests mock at the *coordinator boundary*, not at raw SSE bytes.
    ``runtime_data.telemetry_coordinator.apply_frame`` is the public seam.
    """
    runtime_data: AbrpData = entry.runtime_data
    runtime_data.telemetry_coordinator.apply_frame(frame)


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_abrp_client", "mock_sse_client"
)
async def test_telemetry_sensors_snapshot(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Entity registry shows all 3 telemetry sensors with scoped unique_ids.

    The snapshot pins:

    * Three telemetry sensors per selected vehicle (soc / power / voltage)
      alongside the ``vehicle_model`` diagnostic sensor.
    * Each unique_id scoped by ``entry.unique_id`` —
      ``f"{sub}_{vehicle_id}_{description.key}"`` — so two ABRP accounts
      on one HA can't collide.
    * ``device_class``, ``state_class``, ``unit_of_measurement``, and
      ``entity_category`` per the SENSORS registry.
    """
    await _setup_integration(hass, config_entry_with_vehicles)

    # Seed the telemetry coordinator with one full frame so the snapshot
    # captures the rendered states (not just registry metadata). Freeze
    # time around the frame push (post-setup) so the new ``last_reported_at``
    # attribute stamped by ``apply_frame`` is deterministic in the snapshot.
    # Context-manager scope
    # — applied AFTER setup completes to avoid the prewarm-sleep deadlock.
    with freeze_time("2026-05-24T12:00:00+00:00"):
        _push_telemetry_frame(
            config_entry_with_vehicles,
            build_telemetry_frame(
                MOCK_VEHICLE_ID,
                soc=0.85,
                power=23300.0,
                voltage=704.0,
                # Wake-only telemetry fields land in the snapshot via the
                # same frame so the registry capture covers both sensors.
                range_m=100000.0,
                battery_temp_c=23.7,
                # ENUM sensor: seeded so its registry shape (device_class=enum,
                # options, no state_class/unit) is pinned in the snapshot.
                charging_state="CHARGING_AC",
            ),
        )
        await hass.async_block_till_done()

    await snapshot_platform(
        hass, entity_registry, snapshot, config_entry_with_vehicles.entry_id
    )


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_abrp_client", "mock_sse_client"
)
async def test_soc_scaled_to_percent_with_one_dp(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
) -> None:
    """SoC ``frac`` field is multiplied by 100 and rendered with 1 decimal place.

    Computed shape: ``round(d["soc"]["frac"] * 100, 1)``.
    ``0.857`` → ``85.7`` (one dp).
    """
    await _setup_integration(hass, config_entry_with_vehicles)

    _push_telemetry_frame(
        config_entry_with_vehicles,
        build_telemetry_frame(MOCK_VEHICLE_ID, soc=0.857),
    )
    await hass.async_block_till_done()

    state = hass.states.get(SOC_ENTITY_ID)
    assert state is not None
    assert state.state == "85.7"


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_abrp_client", "mock_sse_client"
)
async def test_partial_update_merge_retains_prior_metrics(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
) -> None:
    """Per-metric frames merge; unchanged metrics keep their previous state.

    Wire frames are deltas: a power-only event must not zero out the
    previously-received soc. This is observable at the *entity* layer —
    after pushing a soc-only frame the soc sensor reflects it, then a
    power-only frame leaves the soc state unchanged.
    """
    await _setup_integration(hass, config_entry_with_vehicles)

    _push_telemetry_frame(
        config_entry_with_vehicles,
        build_telemetry_frame(MOCK_VEHICLE_ID, soc=0.5),
    )
    await hass.async_block_till_done()
    assert hass.states.get(SOC_ENTITY_ID).state == "50.0"

    _push_telemetry_frame(
        config_entry_with_vehicles,
        build_telemetry_frame(MOCK_VEHICLE_ID, power=12000.0),
    )
    await hass.async_block_till_done()

    assert hass.states.get(SOC_ENTITY_ID).state == "50.0"
    assert hass.states.get(POWER_ENTITY_ID).state == "12000.0"


# An absent metric produces NO entity (not an entity with state ``unknown``).
# That "no entity created" behaviour is pinned in ``test_lazy_sensors.py``;
# the underlying ``apply_frame`` null-filter semantics are pinned at the
# coordinator layer in ``test_coordinator.py::test_apply_frame_skips_*``.


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_abrp_client", "mock_sse_client"
)
async def test_partial_update_retains_prior_on_null_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
) -> None:
    """Regression: a null leaf in a delta must not clobber the prior good value.

    Bug walk-through: the user's screenshot showed all live sensors greyed
    out after some upstream events. Root cause: ``apply_frame`` shallow-
    overlays the frame, so a delta containing ``{"power": null}`` overwrites
    the previously-merged ``{"power": {"w": 50000.0}}`` with ``None`` —
    ``value_fn`` then returns ``None`` and the sensor flips unavailable.

    Fix invariant: a null leaf in a frame means "no update for this metric
    in this delta" — equivalent to the key being omitted entirely. After
    frame A ``{soc=0.42, power=50000}`` then frame B ``{"power": null}`` the
    SoC sensor must still read ``"42.0"`` and Power ``"50000.0"``.
    """
    await _setup_integration(hass, config_entry_with_vehicles)

    _push_telemetry_frame(
        config_entry_with_vehicles,
        build_telemetry_frame(MOCK_VEHICLE_ID, soc=0.42, power=50000.0),
    )
    await hass.async_block_till_done()
    assert hass.states.get(SOC_ENTITY_ID).state == "42.0"
    assert hass.states.get(POWER_ENTITY_ID).state == "50000.0"

    _push_telemetry_frame(
        config_entry_with_vehicles,
        {"vehicleId": MOCK_VEHICLE_ID, "power": None},
    )
    await hass.async_block_till_done()

    assert hass.states.get(SOC_ENTITY_ID).state == "42.0"
    assert hass.states.get(POWER_ENTITY_ID).state == "50000.0"


# ---------- Range + Battery Temperature sensors ----------------------------
#
# * Range: wire key ``estimatedBatteryRange.m`` (meters, float). HA
#   ``translation_key="range"``. DISTANCE class, MEASUREMENT state_class
#   (instantaneous level, not accumulating). Native ``m``, suggested unit
#   ``km`` with display precision 0 — mirrors odometer's unit-conversion
#   shape so the user reads km on the dashboard while the recorder keeps
#   the canonical meter scale for unit-flip safety.
# * Battery Temperature: wire key ``batteryTemperature.c`` (Celsius,
#   float). HA ``translation_key="battery_temperature"``. TEMPERATURE
#   class, MEASUREMENT state_class. Display precision 1 — one decimal is
#   enough to read true thermal fluctuation without fake precision.
#
# Both inherit ``AbrpRestorableTelemetrySensor``'s RestoreSensor +
# ``last_reported_at`` semantics automatically — no restoration-specific
# test surface added here. The wake-only character of these metrics
# (Range can update mid-drive; Battery Temp may persist during thermal-
# management cycles) is implicitly covered by the ``test_restore.py``
# trajectory matrix.
#
# Entity_id slug rendering (``has_entity_name=True`` + device name +
# translation_key):
#   sensor.rivian_r2_2027_standard_long_range_range
#   sensor.rivian_r2_2027_standard_long_range_battery_temperature
#
# The "range_range" doubling in the Range entity_id is the natural
# consequence of the device name containing "range" and the
# translation_key being "range"; HA sensor key = ``range`` remains
# authoritative.


RANGE_ENTITY_ID = "sensor.rivian_r2_2027_standard_long_range_range"
BATTERY_TEMP_ENTITY_ID = "sensor.rivian_r2_2027_standard_long_range_battery_temperature"


@pytest.mark.parametrize(
    ("range_m", "expected_state"),
    [
        pytest.param(100000.0, "100.0", id="100km_typical"),
        pytest.param(50000.0, "50.0", id="50km_half_range"),
        pytest.param(0.0, "0.0", id="empty_battery"),
        pytest.param(523456.0, "523.456", id="long_range_truncates_to_km"),
    ],
)
@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_abrp_client", "mock_sse_client"
)
async def test_range_sensor_state(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    range_m: float,
    expected_state: str,
) -> None:
    """Range sensor surfaces ``estimatedBatteryRange.m`` rendered in km.

    Native ``METERS`` + ``suggested_unit_of_measurement=KILOMETERS`` +
    ``suggested_display_precision=0`` mirror the existing odometer
    sensor's wire-meters-to-display-km translation, so the user sees a
    familiar km value on the dashboard while the LTS pipeline keeps the
    canonical meter scale for unit-flip / locale conversions.

    The entity surfaces on the first frame carrying the field via the
    ``_estimated_battery_range_m`` value_fn registered in ``SENSORS``.
    """
    await _setup_integration(hass, config_entry_with_vehicles)

    _push_telemetry_frame(
        config_entry_with_vehicles,
        build_telemetry_frame(MOCK_VEHICLE_ID, range_m=range_m),
    )
    await hass.async_block_till_done()

    state = hass.states.get(RANGE_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("temp_c", "expected_state"),
    [
        pytest.param(23.7, "23.7", id="warm_typical"),
        pytest.param(0.0, "0.0", id="freezing_point"),
        pytest.param(-10.5, "-10.5", id="cold_winter"),
        pytest.param(45.2, "45.2", id="dc_fast_charge_warm"),
    ],
)
@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_abrp_client", "mock_sse_client"
)
async def test_battery_temperature_sensor_state(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    temp_c: float,
    expected_state: str,
) -> None:
    """Battery Temperature sensor surfaces ``batteryTemperature.c`` in °C.

    Native unit is Celsius; ``suggested_display_precision=1`` gives one
    decimal place — enough to read meaningful thermal fluctuation
    (charging warm-up, ambient pre-conditioning) without inflating
    noise. Negative values are pinned because winter operation is a
    real wire shape, not a degenerate one.

    The entity surfaces on the first frame carrying the field via the
    ``_battery_temperature_c`` value_fn registered in ``SENSORS``.
    """
    await _setup_integration(hass, config_entry_with_vehicles)

    _push_telemetry_frame(
        config_entry_with_vehicles,
        build_telemetry_frame(MOCK_VEHICLE_ID, battery_temp_c=temp_c),
    )
    await hass.async_block_till_done()

    state = hass.states.get(BATTERY_TEMP_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


# ---------- value_fn null-safety unit tests --------------------------------
#
# Defense-in-depth for the lazy presence-predicate path. The coordinator
# calls these directly on every SSE frame so a missing isinstance guard
# would propagate a TypeError into the SSE consumer task. The full HA setup
# isn't needed — these are pure functions over the wire shape.


@pytest.mark.parametrize(
    ("value_fn", "frame", "expected"),
    [
        # Happy path.
        pytest.param(_soc_percent, {"soc": {"frac": 0.5}}, 50.0, id="soc_ok"),
        pytest.param(_power_w, {"power": {"w": 1234.0}}, 1234.0, id="power_ok"),
        pytest.param(_voltage_v, {"voltage": {"v": 400.0}}, 400.0, id="voltage_ok"),
        # Key absent — most common upstream-delta case.
        pytest.param(_soc_percent, {}, None, id="soc_absent"),
        pytest.param(_power_w, {}, None, id="power_absent"),
        pytest.param(_voltage_v, {}, None, id="voltage_absent"),
        # Key present but value is null (upstream sentinel).
        pytest.param(_soc_percent, {"soc": None}, None, id="soc_null"),
        pytest.param(_power_w, {"power": None}, None, id="power_null"),
        pytest.param(_voltage_v, {"voltage": None}, None, id="voltage_null"),
        # Key present but value is empty dict (no inner field).
        pytest.param(_soc_percent, {"soc": {}}, None, id="soc_empty"),
        pytest.param(_power_w, {"power": {}}, None, id="power_empty"),
        pytest.param(_voltage_v, {"voltage": {}}, None, id="voltage_empty"),
        # Inner numeric leaf is null — ``null * 100`` would TypeError if the
        # isinstance guard were absent.
        pytest.param(_soc_percent, {"soc": {"frac": None}}, None, id="soc_inner_null"),
        pytest.param(_power_w, {"power": {"w": None}}, None, id="power_inner_null"),
        pytest.param(
            _voltage_v, {"voltage": {"v": None}}, None, id="voltage_inner_null"
        ),
        # Inner leaf is the wrong type — bool is a subclass of int in Python,
        # so the explicit ``isinstance(_, bool)`` check matters.
        pytest.param(_soc_percent, {"soc": {"frac": True}}, None, id="soc_inner_bool"),
        pytest.param(_power_w, {"power": {"w": "5000"}}, None, id="power_inner_str"),
        # ENUM charging_state: every degenerate / unrecognized shape maps to
        # ``None`` (never a raw string — an out-of-``options`` value makes HA
        # core raise ``ValueError`` at state write).
        pytest.param(_charging_state, {}, None, id="charging_state_absent"),
        pytest.param(
            _charging_state, {"chargingState": None}, None, id="charging_state_null"
        ),
        pytest.param(
            _charging_state, {"chargingState": {}}, None, id="charging_state_empty"
        ),
        pytest.param(
            _charging_state,
            {"chargingState": {"time": "2026-05-24T12:00:00Z"}},
            None,
            id="charging_state_missing_state",
        ),
        pytest.param(
            _charging_state,
            {"chargingState": {"state": None}},
            None,
            id="charging_state_inner_null",
        ),
        pytest.param(
            _charging_state,
            {"chargingState": {"state": ""}},
            None,
            id="charging_state_inner_empty_string",
        ),
        pytest.param(
            _charging_state,
            {"chargingState": {"state": 123}},
            None,
            id="charging_state_inner_int",
        ),
        pytest.param(
            _charging_state,
            {"chargingState": {"state": "FOO"}},
            None,
            id="charging_state_unrecognized_member",
        ),
    ],
)
def test_value_fn_null_safety(
    value_fn: Callable[[dict[str, Any]], float | str | None],
    frame: dict[str, Any],
    expected: float | str | None,
) -> None:
    """Each value_fn returns ``None`` for every degenerate wire shape."""
    assert value_fn(frame) == expected


# ---------------------------------------------------------------------------
# DeviceInfo.model: computed via catalog prefix-match
# ---------------------------------------------------------------------------
#
# The catalog's display metadata is composed once into a single
# ``device_model: str | None`` column on :class:`AbrpVehicle` and surfaced
# via :attr:`DeviceInfo.model` on the per-vehicle device. Resolution is by
# longest-typecode-prefix-match (not exact ``dict.get``) so a vehicle
# whose typecode is a suffix-decorated variant of a catalog ancestor
# still resolves.
#
# Tests pin via the entity_registry surface (translation_key / unique_id
# / entity_category as registry-options fields). Strings.json slug
# choices stay decoupled from the assertions — translation_keys are the
# contract.


def _make_vehicle(
    *,
    vehicle_id: int = MOCK_VEHICLE_ID,
    name: str | None = "Rivian R2 2027 Standard Long Range",
    vehicle_model: str = MOCK_VEHICLE_MODEL,
    paint: str | None = "WHITE",
) -> AbrpVehicle:
    """Build an AbrpVehicle with identity fields only.

    :class:`AbrpVehicle` carries identity fields plus a single
    ``device_model`` column populated by :func:`_enrich_with_catalog` (no
    per-field catalog columns). For tests that don't exercise catalog
    enrichment directly this builder constructs the minimal vehicle with
    ``device_model`` defaulting to ``None``.
    """
    return AbrpVehicle(
        vehicle_id=vehicle_id,
        name=name,
        vehicle_model=vehicle_model,
        paint=paint,
    )


def _scope(entry: MockConfigEntry, vehicle_id: int) -> str:
    """Build the unique_id / device-identifier prefix for one vehicle."""
    return f"{entry.unique_id}_{vehicle_id}"


def _lookup_sensor_entity_id(
    entity_registry: er.EntityRegistry,
    entry: MockConfigEntry,
    vehicle_id: int,
    translation_key: str,
) -> str | None:
    """Return the entity_id for a per-vehicle sensor, or ``None`` if absent.

    Lookup keyed by the integration's convention ``unique_id`` shape
    ``f"{scope}_{translation_key}"``. Decoupled from ``strings.json``
    slug choices so a friendly-name change doesn't ripple through the
    assertions.
    """
    return entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{_scope(entry, vehicle_id)}_{translation_key}"
    )


# ---- DeviceInfo.model: computed via catalog prefix-match --------


# Vehicle typecode with paint+option suffix decoration. The catalog
# carries the ancestor ``rivian:r1s:25:c3-53g:dual`` — legacy
# ``dict.get(raw.vehicle_model)`` misses, current longest-prefix match
# resolves correctly.
_PREFIX_MATCH_VEHICLE_MODEL = "rivian:r1s:25:c3-53g:dual:perf"
_PREFIX_MATCH_DEVICE_MODEL = "Rivian R1S 2025 Dual Motor"


def _build_prefix_match_catalog() -> dict[str, CatalogEntry]:
    """Build a catalog dict with one prefix-matchable entry for the test vehicle.

    The entry's typecode (``rivian:r1s:25:c3-53g:dual``) is a strict
    prefix of :data:`_PREFIX_MATCH_VEHICLE_MODEL` — the user's vehicle adds
    a ``:perf`` suffix the catalog doesn't carry. current
    :func:`_compute_device_model` resolves via longest-prefix-match;
    legacy ``catalog.get(raw.vehicle_model)`` misses (exact-key only) so
    ``DeviceInfo.model`` falls back to the raw typecode.
    """
    return {
        "rivian:r1s:25:c3-53g:dual": CatalogEntry(
            typecode="rivian:r1s:25:c3-53g:dual",
            manufacturer="Rivian",
            model="R1S",
            title="Dual Motor",
            start_year=2025,
            end_year=None,
            battery_capacity_wh=None,
        ),
    }


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_sse_client")
async def test_device_info_model_uses_catalog_prefix_match(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    mock_abrp_client: AsyncMock,
) -> None:
    """``DeviceInfo.model`` reflects the prefix-matched composed display string.

    The user's vehicle typecode is a suffix-decorated variant of an
    ancestor catalog entry. The pure
    helper :func:`_compute_device_model` resolves to the
    longest-prefix-matching catalog row and composes
    ``"{manufacturer} {model} {year} {title}"``; the result lands on
    the per-vehicle device's ``DeviceInfo.model`` slot.
    """
    mock_abrp_client.return_value = [
        _make_vehicle(vehicle_model=_PREFIX_MATCH_VEHICLE_MODEL)
    ]

    with patch(
        "homeassistant.components.abetterrouteplanner.api.AbrpClient.async_get_catalog",
        return_value=_build_prefix_match_catalog(),
    ):
        await _setup_integration(hass, config_entry_with_vehicles)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, _scope(config_entry_with_vehicles, MOCK_VEHICLE_ID))}
    )
    assert device is not None
    assert device.model == _PREFIX_MATCH_DEVICE_MODEL


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_sse_client")
async def test_device_info_model_falls_back_to_typecode_on_catalog_miss(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    mock_abrp_client: AsyncMock,
) -> None:
    """``DeviceInfo.model`` falls back to the raw typecode on catalog miss.

    The default ``mock_abrp_client`` fixture mocks the catalog to an
    empty dict, so :func:`_compute_device_model` returns ``None`` for
    every typecode → ``vehicle.device_model`` stays ``None`` →
    ``DeviceInfo.model`` falls back to ``vehicle.vehicle_model`` (raw
    typecode). The device card's Model field is never blank.
    """
    mock_abrp_client.return_value = [_make_vehicle()]

    await _setup_integration(hass, config_entry_with_vehicles)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, _scope(config_entry_with_vehicles, MOCK_VEHICLE_ID))}
    )
    assert device is not None
    assert device.model == MOCK_VEHICLE_MODEL


# Two-make catalog used by the per-vehicle manufacturer test below. The
# second entry sits under a distinct ``polestar:2`` ancestor so the two
# selected vehicles resolve to different manufacturers — a single-make
# catalog couldn't distinguish "manufacturer per-vehicle bound" from "hard-coded
# to the first catalog entry's make."
_POLESTAR_VEHICLE_MODEL = "polestar:2:24:bev:awd"


def _build_two_make_catalog() -> dict[str, CatalogEntry]:
    """Build a catalog with two distinct-manufacturer prefix-matchable entries.

    ``rivian:r2`` matches :data:`MOCK_VEHICLE_MODEL`
    (``rivian:r2:26:ncma91:rwd:w21``); ``polestar:2`` matches
    :data:`_POLESTAR_VEHICLE_MODEL`. Both entries carry their own make so
    each per-vehicle device's ``DeviceInfo.manufacturer`` can be pinned
    independently.
    """
    return {
        "rivian:r2": CatalogEntry(
            typecode="rivian:r2",
            manufacturer="Rivian",
            model="R2",
            title=None,
            start_year=2026,
            end_year=None,
            battery_capacity_wh=None,
        ),
        "polestar:2": CatalogEntry(
            typecode="polestar:2",
            manufacturer="Polestar",
            model="2",
            title=None,
            start_year=2024,
            end_year=None,
            battery_capacity_wh=None,
        ),
    }


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_sse_client")
async def test_device_info_manufacturer_uses_catalog_make(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    device_registry: dr.DeviceRegistry,
    mock_abrp_client: AsyncMock,
) -> None:
    """Each per-vehicle device's ``manufacturer`` reflects its catalog-derived make.

    Two vehicles whose typecodes resolve to two distinct catalog makes
    prove per-instance binding of ``DeviceInfo.manufacturer`` (not
    hard-coded-to-first or hard-coded-to-integration-name).
    """
    mock_abrp_client.return_value = [
        _make_vehicle(),
        _make_vehicle(
            vehicle_id=MOCK_VEHICLE_ID_2,
            vehicle_model=_POLESTAR_VEHICLE_MODEL,
        ),
    ]
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SENSOR_TEST_SUB,
        data={
            "auth_implementation": DOMAIN,
            "token": token_entry,
            CONF_VEHICLE_IDS: [str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)],
        },
    )

    with patch(
        "homeassistant.components.abetterrouteplanner.api.AbrpClient.async_get_catalog",
        return_value=_build_two_make_catalog(),
    ):
        await _setup_integration(hass, entry)

    expected_makes = {
        MOCK_VEHICLE_ID: "Rivian",
        MOCK_VEHICLE_ID_2: "Polestar",
    }
    for vehicle_id, manufacturer in expected_makes.items():
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, f"{SENSOR_TEST_SUB}_{vehicle_id}")}
        )
        assert device is not None
        assert device.manufacturer == manufacturer


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_abrp_client", "mock_sse_client"
)
async def test_device_info_manufacturer_falls_back_to_integration_name_on_catalog_miss(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """``DeviceInfo.manufacturer`` falls back to the integration name on catalog miss.

    The default ``mock_abrp_client`` fixture mocks the catalog to an
    empty dict, so every typecode misses → ``vehicle.device_manufacturer``
    stays ``None`` → ``DeviceInfo.manufacturer`` falls back to the
    integration's user-visible name. The device card's Manufacturer
    field is never blank.
    """
    await _setup_integration(hass, config_entry_with_vehicles)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, _scope(config_entry_with_vehicles, MOCK_VEHICLE_ID))}
    )
    assert device is not None
    assert device.manufacturer == "A Better Routeplanner"


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_abrp_client", "mock_sse_client"
)
async def test_device_info_configuration_url_is_per_vehicle_deep_link(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    device_registry: dr.DeviceRegistry,
) -> None:
    """Each per-vehicle device's ``configuration_url`` deep-links to its own ABRP page.

    Two distinct vehicles are selected so the assertion proves per-instance
    binding of ``configuration_url`` rather than a coincidental match
    against a single id substring.
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

    await _setup_integration(hass, entry)

    for vehicle_id in (MOCK_VEHICLE_ID, MOCK_VEHICLE_ID_2):
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, f"{SENSOR_TEST_SUB}_{vehicle_id}")}
        )
        assert device is not None
        assert (
            device.configuration_url
            == f"https://abetterrouteplanner.com/?vehicle_id={vehicle_id}"
        )


# ---- Sensor-bucket UX: telemetry sensors promoted to the primary bucket ---


# Per-sensor wire-shape payload sufficient to lazy-create the entity.
_DIAGNOSTIC_FRAME_BY_KEY: dict[str, dict[str, Any]] = {
    "voltage": {"voltage": {"v": 704.0}},
    "calibrated_ref_cons": {"calibratedRefCons": {"wh_per_km": 175.0}},
    "battery_capacity": {"batteryCapacity": {"wh": 75000.0}},
    "soh": {"soh": {"frac": 0.92}},
}


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_abrp_client", "mock_sse_client"
)
@pytest.mark.parametrize(
    "sensor_key",
    [
        pytest.param("voltage", id="voltage"),
        pytest.param("calibrated_ref_cons", id="calibrated_ref_cons"),
        pytest.param("battery_capacity", id="battery_capacity"),
        pytest.param("soh", id="soh"),
    ],
)
async def test_diagnostic_telemetry_sensors_moved_out_of_diagnostic(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    sensor_key: str,
) -> None:
    """Four telemetry sensors no longer carry ``EntityCategory.DIAGNOSTIC``.

    Voltage, Calibrated Ref Cons, Battery Capacity, and State of Health
    move from the device card's diagnostic drawer into the main sensor
    bucket. ``entity_category`` is a registry-options field; assert via
    ``entity_registry.async_get(...).entity_category``, not via
    ``state.attributes`` (which omits the field when it is ``None``).
    """
    frame_payload = _DIAGNOSTIC_FRAME_BY_KEY[sensor_key]

    await _setup_integration(hass, config_entry_with_vehicles)
    _push_telemetry_frame(
        config_entry_with_vehicles,
        {"vehicleId": MOCK_VEHICLE_ID, **frame_payload},
    )
    await hass.async_block_till_done()

    entity_id = _lookup_sensor_entity_id(
        entity_registry, config_entry_with_vehicles, MOCK_VEHICLE_ID, sensor_key
    )
    assert entity_id is not None
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.entity_category is None


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_abrp_client", "mock_sse_client"
)
async def test_calibrated_ref_cons_renamed_to_short_form(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """The Calibrated Ref Cons sensor's friendly name translates to the short form.

    The device card width is dominated by the longest sensor name; the
    full ``Calibrated Reference Consumption`` wraps or truncates on
    narrow viewports. The translation string shortens to
    ``Calibrated Ref Cons``. Asserted via the registry's
    ``original_name`` — the resolved translation at registration time,
    independent of friendly-name composition with the device prefix.
    """
    await _setup_integration(hass, config_entry_with_vehicles)
    _push_telemetry_frame(
        config_entry_with_vehicles,
        {"vehicleId": MOCK_VEHICLE_ID, "calibratedRefCons": {"wh_per_km": 175.0}},
    )
    await hass.async_block_till_done()

    entity_id = _lookup_sensor_entity_id(
        entity_registry,
        config_entry_with_vehicles,
        MOCK_VEHICLE_ID,
        "calibrated_ref_cons",
    )
    assert entity_id is not None
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.original_name == "Calibrated Ref Cons"


# ---- Device anchor at setup + Type Code sensor absence -------------------


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_sse_client")
async def test_per_vehicle_device_anchored_at_setup(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    device_registry: dr.DeviceRegistry,
    mock_abrp_client: AsyncMock,
) -> None:
    """Each selected vehicle's device exists with full metadata after setup completes.

    The per-vehicle device is anchored to the entry at setup time —
    before any telemetry entity is created — so the device card is
    present immediately and survives a vehicle going silent (no
    telemetry frames). Two distinct vehicles with two distinct catalog
    makes prove per-instance binding of every device-info field
    (``manufacturer``, ``model``, ``name``, ``configuration_url``).
    """
    polestar_name = "Polestar 2 Long Range"
    mock_abrp_client.return_value = [
        _make_vehicle(),
        _make_vehicle(
            vehicle_id=MOCK_VEHICLE_ID_2,
            name=polestar_name,
            vehicle_model=_POLESTAR_VEHICLE_MODEL,
        ),
    ]
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SENSOR_TEST_SUB,
        data={
            "auth_implementation": DOMAIN,
            "token": token_entry,
            CONF_VEHICLE_IDS: [str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)],
        },
    )

    with patch(
        "homeassistant.components.abetterrouteplanner.api.AbrpClient.async_get_catalog",
        return_value=_build_two_make_catalog(),
    ):
        await _setup_integration(hass, entry)

    expected_by_vehicle: dict[int, dict[str, str]] = {
        MOCK_VEHICLE_ID: {
            "manufacturer": "Rivian",
            "model": "Rivian R2 2026",
            "name": "Rivian R2 2027 Standard Long Range",
            "configuration_url": (
                f"https://abetterrouteplanner.com/?vehicle_id={MOCK_VEHICLE_ID}"
            ),
        },
        MOCK_VEHICLE_ID_2: {
            "manufacturer": "Polestar",
            "model": "Polestar 2 2024",
            "name": polestar_name,
            "configuration_url": (
                f"https://abetterrouteplanner.com/?vehicle_id={MOCK_VEHICLE_ID_2}"
            ),
        },
    }
    for vehicle_id, expected in expected_by_vehicle.items():
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, f"{SENSOR_TEST_SUB}_{vehicle_id}")}
        )
        assert device is not None
        assert device.manufacturer == expected["manufacturer"]
        assert device.model == expected["model"]
        assert device.name == expected["name"]
        assert device.configuration_url == expected["configuration_url"]


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_abrp_client", "mock_sse_client"
)
async def test_no_type_code_entity_created(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """No entity with a ``_type_code`` unique-id suffix is registered.

    The catalog model name (with raw-typecode fallback) surfaces only
    via ``DeviceInfo.model`` on the per-vehicle device card; there is
    no standalone Type Code sensor. Asserts the absence by enumerating
    every registry entry for the config entry and confirming none of
    their unique_ids end with ``_type_code``.
    """
    await _setup_integration(hass, config_entry_with_vehicles)

    entries = er.async_entries_for_config_entry(
        entity_registry, config_entry_with_vehicles.entry_id
    )
    type_code_entries = [
        registry_entry
        for registry_entry in entries
        if registry_entry.unique_id.endswith("_type_code")
    ]
    assert type_code_entries == []


# ---------------------------------------------------------------------------
# chargingState ENUM sensor
# ---------------------------------------------------------------------------
#
# A single ``SensorDeviceClass.ENUM`` sensor surfacing the categorical
# ``chargingState`` wire field (CHARGING_AC / CHARGING_DC /
# CHARGING_UNKNOWN / NOT_CHARGING / PLUGGED_IN). Mapped to lowercase HA
# option keys; unknown / malformed members map to ``None`` (never a raw
# string — an out-of-``options`` value makes HA core raise ``ValueError``
# at state write). Shares the generic telemetry-sensor base, so lazy
# create + restore + ``last_reported_at`` / ``provider`` attributes come
# for free.


@pytest.mark.parametrize(
    ("wire_state", "expected_option"),
    [
        pytest.param("CHARGING_AC", "charging_ac", id="charging_ac"),
        pytest.param("CHARGING_DC", "charging_dc", id="charging_dc"),
        pytest.param("CHARGING_UNKNOWN", "charging_unknown", id="charging_unknown"),
        pytest.param("NOT_CHARGING", "not_charging", id="not_charging"),
        pytest.param("PLUGGED_IN", "plugged_in", id="plugged_in"),
    ],
)
def test_charging_state_value_fn_maps_all_wire_members(
    wire_state: str,
    expected_option: str,
) -> None:
    """Every wire enum member maps to its lowercase HA option key.

    Pure value_fn contract over the 5-member closed enum. Pairs with the
    cross-pin guard (which proves the option set stays in sync with the
    ``ChargingStateValue`` literal, the entity description ``options``, and
    the ``strings.json`` / ``icons.json`` per-state maps).
    """
    frame: dict[str, Any] = {"chargingState": {"state": wire_state}}
    assert _charging_state(frame) == expected_option


@pytest.mark.parametrize(
    ("wire_state", "expected_option"),
    [
        pytest.param("CHARGING_AC", "charging_ac", id="charging_ac"),
        pytest.param("NOT_CHARGING", "not_charging", id="not_charging"),
        pytest.param("PLUGGED_IN", "plugged_in", id="plugged_in"),
    ],
)
@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_abrp_client", "mock_sse_client"
)
async def test_charging_state_lazy_create_via_dispatcher(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    wire_state: str,
    expected_option: str,
) -> None:
    """First ``chargingState`` frame after setup lazily creates the enum sensor.

    Routes the frame through ``apply_frame`` *after* the platform has
    registered its presence predicates, exercising the dispatcher
    ``_on_new_metric`` path (the primary path for an event-driven field
    rarely present in the seed snapshot). The entity must be absent before
    the frame and surface the mapped lowercase option afterwards.
    """
    await _setup_integration(hass, config_entry_with_vehicles)

    # Negation: no chargingState frame yet → no entity.
    assert hass.states.get(CHARGING_STATE_ENTITY_ID) is None

    _push_telemetry_frame(
        config_entry_with_vehicles,
        build_telemetry_frame(MOCK_VEHICLE_ID, charging_state=wire_state),
    )
    await hass.async_block_till_done()

    state = hass.states.get(CHARGING_STATE_ENTITY_ID)
    assert state is not None
    assert state.state == expected_option


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_abrp_client", "mock_sse_client"
)
async def test_charging_state_registry_shape(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
) -> None:
    """The enum sensor is ENUM device_class, the 5 options, and no state_class.

    Pins the static description shape (mirrors the ``battery_capacity``
    static-pin precedent for ``state_class is None`` so a future
    copy-paste from a numeric sensor can't attach one). ENUM sensors carry
    no unit and are LTS-ineligible.
    """
    description = SENSORS_BY_KEY["charging_state"]
    assert description.device_class is SensorDeviceClass.ENUM
    assert description.options == list(_CHARGING_STATE_OPTIONS.values())
    assert description.state_class is None
    assert description.native_unit_of_measurement is None

    await _setup_integration(hass, config_entry_with_vehicles)
    _push_telemetry_frame(
        config_entry_with_vehicles,
        build_telemetry_frame(MOCK_VEHICLE_ID, charging_state="CHARGING_AC"),
    )
    await hass.async_block_till_done()

    state = hass.states.get(CHARGING_STATE_ENTITY_ID)
    assert state is not None
    assert state.attributes["device_class"] == SensorDeviceClass.ENUM
    assert state.attributes["options"] == list(_CHARGING_STATE_OPTIONS.values())
    assert "state_class" not in state.attributes
    assert "unit_of_measurement" not in state.attributes


def test_charging_state_warns_once_on_unrecognized(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An unrecognized non-empty wire member logs WARNING exactly once.

    Upstream enum drift (a future member the integration hasn't mapped)
    must leave a runtime breadcrumb — diagnostics surfaces field names but
    not values. The warning is deduped via the module-level
    ``_unknown_charging_states_seen`` set so a high-frequency stream of the
    same unknown member doesn't spam the log. The value_fn still returns
    ``None`` (never the raw string).

    The ``_unknown_charging_states_seen`` global is reset around every test
    by the autouse ``_isolate_unknown_charging_states`` fixture, so this
    test starts from a clean dedup state regardless of run order.
    """
    unknown_frame: dict[str, Any] = {"chargingState": {"state": "WARP_DRIVE"}}

    with caplog.at_level(
        logging.WARNING, logger="homeassistant.components.abetterrouteplanner"
    ):
        assert _charging_state(unknown_frame) is None
        first = [
            record
            for record in caplog.records
            if record.levelno == logging.WARNING and "WARP_DRIVE" in record.getMessage()
        ]
        assert len(first) == 1

        # Second occurrence of the SAME member must NOT re-log.
        assert _charging_state(unknown_frame) is None
        second = [
            record
            for record in caplog.records
            if record.levelno == logging.WARNING and "WARP_DRIVE" in record.getMessage()
        ]
        assert len(second) == 1


def test_charging_state_empty_string_does_not_warn(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An empty ``state`` maps to ``None`` WITHOUT logging a warning.

    Exercises the ``state and ...`` truthiness short-circuit in the value_fn:
    an empty string is a malformed/blank shape, not an unrecognized future
    member, so it must NOT emit the enum-drift WARNING nor pollute the
    ``_unknown_charging_states_seen`` dedup set (which would otherwise grow
    an empty-string key).
    """
    with caplog.at_level(
        logging.WARNING, logger="homeassistant.components.abetterrouteplanner"
    ):
        assert _charging_state({"chargingState": {"state": ""}}) is None

    assert not any(record.levelno == logging.WARNING for record in caplog.records)
    assert "" not in _unknown_charging_states_seen


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_abrp_client", "mock_sse_client"
)
async def test_charging_state_provider_and_stamp_attributes(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
) -> None:
    """The enum sensor surfaces ``provider`` + ``last_reported_at`` like numerics.

    The generic base composes both attributes for the enum sensor with no
    enum-specific override — a live frame carrying a provider stamps both
    the per-metric ``last_provider`` and ``last_reported_at`` maps, and the
    entity surfaces them.
    """
    await _setup_integration(hass, config_entry_with_vehicles)

    stamp = datetime(2026, 5, 24, 12, 0, 0, tzinfo=UTC)
    with freeze_time(stamp):
        _push_telemetry_frame(
            config_entry_with_vehicles,
            {
                "vehicleId": MOCK_VEHICLE_ID,
                "chargingState": {"state": "CHARGING_DC", "provider": "RIVIAN_STREAM"},
            },
        )
        await hass.async_block_till_done()

    state = hass.states.get(CHARGING_STATE_ENTITY_ID)
    assert state is not None
    assert state.state == "charging_dc"
    assert state.attributes.get("provider") == "RIVIAN_STREAM"
    assert state.attributes.get("last_reported_at") == stamp


# ---- chargingState restore across HA restart -----------------------------


def _charging_restored_state(
    *,
    native_value: str | None = "not_charging",
    last_reported_at: str | None = None,
    provider: str | None = None,
) -> tuple[State, dict[str, Any]]:
    """Build a (State, extra_data) tuple for ``mock_restore_cache_with_extra_data``.

    The ENUM sensor carries no unit, so ``native_unit_of_measurement`` is
    ``None`` in the recorder's extra-data blob. ``native_value`` is the
    lowercase HA option string (what the live path wrote at persist time).
    """
    attributes: dict[str, Any] = {}
    if last_reported_at is not None:
        attributes["last_reported_at"] = last_reported_at
    if provider is not None:
        attributes["provider"] = provider
    state = State(
        CHARGING_STATE_ENTITY_ID,
        native_value if native_value is not None else "unknown",
        attributes=attributes,
    )
    extra_data: dict[str, Any] = {
        "native_value": native_value,
        "native_unit_of_measurement": None,
    }
    return state, extra_data


async def _charging_restart_setup(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    *,
    entity_registry: er.EntityRegistry,
    restored_states: list[tuple[State, dict[str, Any]]] | None = None,
) -> None:
    """Set up the integration simulating an HA restart with a prior enum row.

    Pre-seeds the entity registry with the charging_state row (using the
    slug the integration computes from ``has_entity_name`` + device name +
    translation_key) so the eager-from-registry probe re-creates the entity
    BEFORE the first wake frame, and wires the recorder restore cache.
    """
    hass.set_state(CoreState.not_running)
    if restored_states is not None:
        mock_restore_cache_with_extra_data(hass, restored_states)
    assert await async_setup_component(hass, "auth", {})
    assert await async_setup_component(hass, DOMAIN, {})
    entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id=CHARGING_STATE_UNIQUE_ID,
        config_entry=entry,
        suggested_object_id="rivian_r2_2027_standard_long_range_charging_state",
    )
    with patch(
        "homeassistant.components.abetterrouteplanner.PREWARM_WINDOW_SECONDS",
        0,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("restored_value", "expected_state"),
    [
        pytest.param("not_charging", "not_charging", id="parked_not_charging_survives"),
        pytest.param("charging_ac", "charging_ac", id="in_options_survives"),
        pytest.param(
            "CHARGING_AC", "unavailable", id="wire_form_not_in_options_rejected"
        ),
        pytest.param("bogus", "unavailable", id="unknown_value_rejected"),
    ],
)
@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_charging_state_restore_native_value(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
    restored_value: str,
    expected_state: str,
) -> None:
    """Restored enum state survives restart only when it is a valid option.

    Three trajectories share the restore-setup → assert-state structure:

    - ``parked_not_charging_survives`` — a parked/unplugged vehicle whose
      last seen state was ``not_charging`` restores ``not_charging`` (not
      ``unavailable``) before any wake frame.
    - ``in_options_survives`` — any other in-``options`` string restores
      verbatim.
    - ``wire_form_not_in_options_rejected`` / ``unknown_value_rejected`` —
      a restored value outside ``options`` (the raw UPPER wire member, or
      arbitrary junk) is coerced to ``None`` by
      ``AbrpEnumSensor._restore_native_value`` → entity ``unavailable``.
      This mirrors HA core's ENUM rejection and prevents a ``ValueError``
      at state write.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    await _charging_restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        restored_states=[_charging_restored_state(native_value=restored_value)],
    )

    state = hass.states.get(CHARGING_STATE_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.usefixtures("mock_abrp_client", "mock_sse_client")
async def test_charging_state_restores_provider_and_stamp(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_seed_responses: AsyncMock,
) -> None:
    """Restored ``provider`` + ``last_reported_at`` surface on the enum sensor.

    The enum sensor inherits the shared base's stamp/provider restore, so a
    parked vehicle keeps both attributes across restart without a wake frame.
    """
    mock_seed_responses.responses[MOCK_VEHICLE_ID] = {}

    stamp_iso = "2026-05-20T12:00:00+00:00"
    stamp_dt = datetime(2026, 5, 20, 12, 0, 0, tzinfo=UTC)

    await _charging_restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        restored_states=[
            _charging_restored_state(
                native_value="not_charging",
                last_reported_at=stamp_iso,
                provider="RIVIAN_STREAM",
            )
        ],
    )

    state = hass.states.get(CHARGING_STATE_ENTITY_ID)
    assert state is not None
    assert state.state == "not_charging"
    assert state.attributes.get("provider") == "RIVIAN_STREAM"
    assert state.attributes.get("last_reported_at") == stamp_dt


# ---- cross-pin guard (drift protection) ----------------------------------


def test_charging_state_options_cross_pinned() -> None:
    """The 5-member truth stays in sync across every copy.

    Four copies of the closed enum must agree, or a drift goes RED:

    1. ``_CHARGING_STATE_OPTIONS`` keys ↔ the ``ChargingStateValue`` literal
       members. ``ChargingStateValue`` is a PEP 695 ``type`` alias
       (``TypeAliasType``), so its members live at ``.__value__.__args__`` —
       read via ``get_args(ChargingStateValue.__value__)``.
    2. ``_CHARGING_STATE_OPTIONS`` values ↔ the enum entity description's
       ``options`` list.
    3. + 4. ``_CHARGING_STATE_OPTIONS`` values ↔ the
       ``entity.sensor.charging_state.state`` keyset in BOTH ``strings.json``
       and ``icons.json`` (a missing label / icon silently renders the raw
       option key in the UI). The source files are read directly (not the
       generated ``translations/en.json``).
    """
    assert set(_CHARGING_STATE_OPTIONS) == set(get_args(ChargingStateValue.__value__))

    description = SENSORS_BY_KEY["charging_state"]
    assert set(_CHARGING_STATE_OPTIONS.values()) == set(description.options)

    strings = json.loads(
        (_INTEGRATION_DIR / "strings.json").read_text(encoding="utf-8")
    )
    icons = json.loads((_INTEGRATION_DIR / "icons.json").read_text(encoding="utf-8"))
    strings_states = strings["entity"]["sensor"]["charging_state"]["state"]
    icons_states = icons["entity"]["sensor"]["charging_state"]["state"]
    assert set(_CHARGING_STATE_OPTIONS.values()) == set(strings_states)
    assert set(_CHARGING_STATE_OPTIONS.values()) == set(icons_states)
