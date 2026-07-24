"""Tests for the A Better Routeplanner sensor platform.

Surface under test:

* One HA device per ``vehicle_id`` in ``entry.data[CONF_VEHICLE_IDS]``,
  anchored at integration setup with full DeviceInfo metadata.
* Lazily-created telemetry sensors per device.
* Filter is applied at ``async_setup_entry`` time: vehicles not in
  ``CONF_VEHICLE_IDS`` are dropped silently; selected ``vehicle_id`` values
  missing from the coordinator payload log a warning and skip (no
  entity, no device, no repair issue).

Telemetry data model
--------------------
The coordinator surfaces typed library state, not raw SSE wire frames:
``coordinator.data`` is ``dict[int, dict[Metric, MetricValue]]``. Tests drive
it through the two committed seams in ``conftest.py``:

* ``mock_abrp_client.seed_responses[vid] = {Metric.X: build_metric_value(...)}``
  for the setup-time seed snapshot, and
* ``fake_stream.fire_frame(vid, {Metric.X: build_metric_value(...)})`` for a
  post-setup push frame (the dispatcher / lazy-create path).

Wire-shape parsing, per-metric delta merge, null-leaf retention, and the raw
``chargingState`` member mapping are owned by ``aioabrp`` and covered by the
library's own suite — the integration test only asserts behaviour on the typed
``MetricValue`` boundary.
"""

from datetime import UTC, datetime
import json
import logging
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

from aioabrp import AbrpVehicle, ChargingState, Metric, Telemetry
from freezegun import freeze_time
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import abetterrouteplanner as abrp_module
from homeassistant.components.abetterrouteplanner.const import CONF_VEHICLE_IDS, DOMAIN
from homeassistant.components.abetterrouteplanner.sensor import (
    CHARGING_STATE_OPTIONS,
    SENSORS_BY_METRIC,
)
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
    build_metric_value,
    build_vehicle_model_display,
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


async def _setup_integration(
    hass: HomeAssistant, entry: MockConfigEntry
) -> MockConfigEntry:
    """Register the integration's OAuth implementation and set up the entry.

    Tests that complete setup with a non-empty ``CONF_VEHICLE_IDS`` selection
    MUST also request the ``fake_stream`` fixture: a real
    :class:`aioabrp.TelemetryStream` would otherwise be constructed and try to
    open an SSE connection. ``fake_stream`` patches the stream class with a
    synchronous test double, so setup returns without opening a connection.
    """
    assert await async_setup_component(hass, "auth", {})
    assert await async_setup_component(hass, DOMAIN, {})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_abrp_client", "fake_stream"
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


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_selected_vehicle_missing_from_garage_logs_and_skips(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A selected ``vehicle_id`` missing from the garage emits nothing + logs.

    Mirrors the user-visible behaviour when a vehicle was removed from
    the ABRP account between picker submission and the first coordinator
    refresh: no entity, no device, no repair — just a debug log line.
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
        logging.DEBUG, logger="homeassistant.components.abetterrouteplanner"
    ):
        await _setup_integration(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    assert not er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert not dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    assert bogus_id in caplog.text


# Telemetry sensor tests ------------------------------------------------------


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_abrp_client", "fake_stream"
)
async def test_telemetry_sensors_snapshot(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    fake_stream: Any,
    snapshot: SnapshotAssertion,
) -> None:
    """Entity registry + states snapshot for the full per-vehicle metric set.

    Every metric is fired for the selected vehicle so all 11 telemetry
    entities exist (entity creation is lazy — a metric entity surfaces only
    after its metric first carries a value). The snapshot pins:

    * One entity per metric (soc / power / voltage / soe / odometer /
      calibrated_ref_cons / battery_capacity / soh / range /
      battery_temperature / charging_state).
    * Each unique_id scoped by ``entry.unique_id`` —
      ``f"{sub}_{vehicle_id}_{description.key}"`` — so two ABRP accounts on
      one HA can't collide.
    * ``device_class``, ``state_class``, ``unit_of_measurement``, and
      ``entity_category`` per the SENSORS registry, plus the rendered native
      state and the deterministic ``last_reported_at`` stamp.
    """
    await _setup_integration(hass, config_entry_with_vehicles)

    # Fire one frame carrying EVERY metric so the snapshot captures all
    # entities with rendered states (not just registry metadata). Freeze
    # time around the push so the receipt-stamped ``last_reported_at`` is
    # deterministic. SOC / SOH are PERCENT values on the typed boundary
    # (the library scales the wire ``frac`` before HA sees it). The
    # charging-state metric carries a typed ``ChargingState`` member, mapped
    # to its HA option string by the enum sensor.
    with freeze_time("2026-05-24T12:00:00+00:00"):
        fake_stream.fire_frame(
            MOCK_VEHICLE_ID,
            Telemetry(
                soc=build_metric_value(85.0),
                power=build_metric_value(23300.0),
                voltage=build_metric_value(704.0),
                soe=build_metric_value(68000.0),
                odometer=build_metric_value(120000.0),
                calibrated_ref_cons=build_metric_value(175.0),
                battery_capacity=build_metric_value(92000.0),
                soh=build_metric_value(98.0),
                range=build_metric_value(100000.0),
                battery_temperature=build_metric_value(23.7),
                charging_state=build_metric_value(ChargingState.CHARGING_AC),
            ),
        )
        await hass.async_block_till_done()

    await snapshot_platform(
        hass, entity_registry, snapshot, config_entry_with_vehicles.entry_id
    )


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_abrp_client", "fake_stream"
)
async def test_soc_native_value_is_percent(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    fake_stream: Any,
) -> None:
    """SoC surfaces the typed PERCENT ``MetricValue.value`` with one decimal.

    The library scales the wire ``frac`` to a percentage before HA sees it,
    so the sensor's ``native_value`` is the float percent directly. With
    ``suggested_display_precision=1`` a ``85.7`` percent reading renders as
    ``"85.7"``.
    """
    await _setup_integration(hass, config_entry_with_vehicles)

    fake_stream.fire_frame(MOCK_VEHICLE_ID, Telemetry(soc=build_metric_value(85.7)))
    await hass.async_block_till_done()

    state = hass.states.get(SOC_ENTITY_ID)
    assert state is not None
    assert state.state == "85.7"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "fake_stream")
async def test_seeded_metric_surfaces_at_setup(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_abrp_client: AsyncMock,
) -> None:
    """A metric present in the setup seed snapshot creates its entity eagerly.

    The seed path (``mock_abrp_client.seed_responses``) populates
    ``coordinator.data`` before the platform forwards, so the platform's
    seed-frame scan creates the entity at setup time without a post-setup
    push frame. SOC is a PERCENT value on the typed boundary, so a seeded
    ``42.0`` renders as ``"42.0"``.
    """
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = Telemetry(
        soc=build_metric_value(42.0)
    )

    await _setup_integration(hass, config_entry_with_vehicles)

    state = hass.states.get(SOC_ENTITY_ID)
    assert state is not None
    assert state.state == "42.0"


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_abrp_client", "fake_stream"
)
async def test_available_follows_native_value(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    fake_stream: Any,
) -> None:
    """``available`` tracks ``native_value is not None``.

    A live frame carrying a non-None value makes the sensor available; the
    entity surfaces a rendered state rather than ``unavailable``.
    """
    await _setup_integration(hass, config_entry_with_vehicles)

    fake_stream.fire_frame(
        MOCK_VEHICLE_ID, Telemetry(power=build_metric_value(12000.0))
    )
    await hass.async_block_till_done()

    state = hass.states.get(POWER_ENTITY_ID)
    assert state is not None
    assert state.state != "unavailable"
    assert state.state == "12000.0"


#
# * Range: HA ``translation_key="range"``. DISTANCE class, MEASUREMENT
#   state_class (instantaneous level, not accumulating). Native ``m``,
#   suggested unit ``km`` with display precision 0 — mirrors odometer's
#   unit-conversion shape so the user reads km on the dashboard while the
#   recorder keeps the canonical meter scale for unit-flip safety.
# * Battery Temperature: HA ``translation_key="battery_temperature"``.
#   TEMPERATURE class, MEASUREMENT state_class. Display precision 1 — one
#   decimal is enough to read true thermal fluctuation without fake precision.
#
# The typed ``MetricValue.value`` is the canonical-unit float (meters for
# range, Celsius for battery temperature); HA's unit conversion handles the
# km display.
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
    "entity_registry_enabled_by_default", "mock_abrp_client", "fake_stream"
)
async def test_range_sensor_state(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    fake_stream: Any,
    range_m: float,
    expected_state: str,
) -> None:
    """Range sensor surfaces the meters ``MetricValue.value`` rendered in km.

    Native ``METERS`` + ``suggested_unit_of_measurement=KILOMETERS`` +
    ``suggested_display_precision=0`` mirror the existing odometer
    sensor's meters-to-display-km translation, so the user sees a familiar
    km value on the dashboard while the LTS pipeline keeps the canonical
    meter scale for unit-flip / locale conversions.

    The entity surfaces on the first frame carrying ``Metric.RANGE``.
    """
    await _setup_integration(hass, config_entry_with_vehicles)

    fake_stream.fire_frame(
        MOCK_VEHICLE_ID, Telemetry(range=build_metric_value(range_m))
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
    "entity_registry_enabled_by_default", "mock_abrp_client", "fake_stream"
)
async def test_battery_temperature_sensor_state(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    fake_stream: Any,
    temp_c: float,
    expected_state: str,
) -> None:
    """Battery Temperature sensor surfaces the Celsius ``MetricValue.value``.

    Native unit is Celsius; ``suggested_display_precision=1`` gives one
    decimal place — enough to read meaningful thermal fluctuation
    (charging warm-up, ambient pre-conditioning) without inflating
    noise. Negative values are pinned because winter operation is a
    real shape, not a degenerate one.

    The entity surfaces on the first frame carrying ``Metric.BATTERY_TEMPERATURE``.
    """
    await _setup_integration(hass, config_entry_with_vehicles)

    fake_stream.fire_frame(
        MOCK_VEHICLE_ID, Telemetry(battery_temperature=build_metric_value(temp_c))
    )
    await hass.async_block_till_done()

    state = hass.states.get(BATTERY_TEMP_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


# Each vehicle's device-card model/manufacturer are composed at setup from the
# per-typecode display fetch (``async_get_vehicle_model_display`` →
# ``VehicleModelDisplay.display_name``); a display miss leaves the display
# ``None`` and the card falls back to the raw typecode.
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
    """Build an AbrpVehicle from its four identity fields.

    :class:`AbrpVehicle` carries only ``vehicle_id`` / ``name`` /
    ``vehicle_model`` / ``paint`` — no composed device-card columns. The
    device-card model/manufacturer are composed separately from the
    per-typecode display endpoint, so this builder constructs the minimal
    raw vehicle the integration receives from the garage.
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


# Vehicle typecode with paint+option suffix decoration. The catalog
# carries the ancestor ``rivian:r1s:25:c3-53g:dual`` — legacy
# ``dict.get(raw.vehicle_model)`` misses, current longest-prefix match
# resolves correctly.
_PREFIX_MATCH_VEHICLE_MODEL = "rivian:r1s:25:c3-53g:dual:perf"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "fake_stream")
async def test_device_info_model_uses_display_endpoint(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    mock_abrp_client: AsyncMock,
) -> None:
    """``DeviceInfo.model`` reflects the composed display string.

    The display endpoint resolves the vehicle's typecode to its display
    metadata; the integration lands that display's ``display_name`` on the
    per-vehicle device's ``DeviceInfo.model`` slot. The composition itself is
    the library's concern, so this pins the wiring against the display's own
    ``display_name`` rather than a hardcoded composed literal.
    """
    display = build_vehicle_model_display(
        manufacturer="Rivian",
        model="R1S",
        years="2025",
        title="Dual Motor",
        start_year=2025,
        end_year=None,
    )
    mock_abrp_client.return_value = [
        _make_vehicle(vehicle_model=_PREFIX_MATCH_VEHICLE_MODEL)
    ]
    mock_abrp_client.display_responses[_PREFIX_MATCH_VEHICLE_MODEL] = display

    await _setup_integration(hass, config_entry_with_vehicles)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, _scope(config_entry_with_vehicles, MOCK_VEHICLE_ID))}
    )
    assert device is not None
    assert device.model == display.display_name


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "fake_stream")
async def test_device_info_model_falls_back_to_typecode_on_display_miss(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    mock_abrp_client: AsyncMock,
) -> None:
    """``DeviceInfo.model`` falls back to the raw typecode on display miss.

    The default ``mock_abrp_client`` fixture 404s the display endpoint for
    every typecode, so the display fetch returns ``None`` → ``DeviceInfo.model``
    falls back to the raw ``vehicle_model`` (typecode). The device card's Model
    field is never blank.
    """
    mock_abrp_client.return_value = [_make_vehicle()]

    await _setup_integration(hass, config_entry_with_vehicles)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, _scope(config_entry_with_vehicles, MOCK_VEHICLE_ID))}
    )
    assert device is not None
    assert device.model == MOCK_VEHICLE_MODEL


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "fake_stream")
async def test_device_info_name_falls_back_to_typecode_when_unnamed(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    mock_abrp_client: AsyncMock,
) -> None:
    """``DeviceInfo.name`` falls back to the raw typecode for an unnamed vehicle.

    A vehicle with no user-set nickname (``name=None``) anchors its device with
    ``name = vehicle.name or vehicle.vehicle_model`` → the raw typecode, so the
    device card's Name is never blank.
    """
    mock_abrp_client.return_value = [_make_vehicle(name=None)]

    await _setup_integration(hass, config_entry_with_vehicles)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, _scope(config_entry_with_vehicles, MOCK_VEHICLE_ID))}
    )
    assert device is not None
    assert device.name == MOCK_VEHICLE_MODEL


# Two-make display fixtures used by the per-vehicle manufacturer test below.
# The second vehicle resolves to Polestar so the two selected vehicles have
# distinct manufacturers — a single-make setup couldn't distinguish
# "manufacturer per-vehicle bound" from "hard-coded to first make."
_POLESTAR_VEHICLE_MODEL = "polestar:2:24:bev:awd"


def _set_two_make_displays(mock_abrp_client: AsyncMock) -> None:
    """Register display fixtures for the two distinct-make vehicles.

    ``MOCK_VEHICLE_MODEL`` resolves to Rivian; ``_POLESTAR_VEHICLE_MODEL`` to
    Polestar — so each per-vehicle device's manufacturer/model is pinned
    independently.
    """
    mock_abrp_client.display_responses[MOCK_VEHICLE_MODEL] = (
        build_vehicle_model_display(
            manufacturer="Rivian",
            model="R2",
            years="2026",
            title="",
            start_year=2026,
            end_year=None,
        )
    )
    mock_abrp_client.display_responses[_POLESTAR_VEHICLE_MODEL] = (
        build_vehicle_model_display(
            manufacturer="Polestar",
            model="2",
            years="2024",
            title="",
            start_year=2024,
            end_year=None,
        )
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "fake_stream")
async def test_device_info_manufacturer_uses_display_make(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    device_registry: dr.DeviceRegistry,
    mock_abrp_client: AsyncMock,
) -> None:
    """Each per-vehicle device's ``manufacturer`` reflects its display-derived make.

    Two vehicles whose typecodes resolve to two distinct display makes
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

    _set_two_make_displays(mock_abrp_client)
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
    "entity_registry_enabled_by_default", "mock_abrp_client", "fake_stream"
)
async def test_device_info_manufacturer_unset_on_display_miss(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """``DeviceInfo.manufacturer`` stays unset on display miss.

    The default ``mock_abrp_client`` fixture 404s the display endpoint for
    every typecode → the display fetch returns ``None`` →
    ``DeviceInfo.manufacturer`` is left unset rather than guessed. A blank
    Manufacturer field is preferable to an incorrect make.
    """
    await _setup_integration(hass, config_entry_with_vehicles)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, _scope(config_entry_with_vehicles, MOCK_VEHICLE_ID))}
    )
    assert device is not None
    assert device.manufacturer is None


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_abrp_client", "fake_stream"
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


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_abrp_client", "fake_stream"
)
@pytest.mark.parametrize(
    ("sensor_key", "metric", "value"),
    [
        pytest.param("voltage", Metric.VOLTAGE, 704.0, id="voltage"),
        pytest.param(
            "calibrated_ref_cons",
            Metric.CALIBRATED_REF_CONS,
            175.0,
            id="calibrated_ref_cons",
        ),
        pytest.param(
            "battery_capacity",
            Metric.BATTERY_CAPACITY,
            75000.0,
            id="battery_capacity",
        ),
        pytest.param("soh", Metric.SOH, 92.0, id="soh"),
    ],
)
async def test_diagnostic_telemetry_sensors_moved_out_of_diagnostic(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    fake_stream: Any,
    sensor_key: str,
    metric: Metric,
    value: float,
) -> None:
    """Four telemetry sensors no longer carry ``EntityCategory.DIAGNOSTIC``.

    Voltage, calibrated ref cons, battery capacity, and state of health
    move from the device card's diagnostic drawer into the main sensor
    bucket. ``entity_category`` is a registry-options field; assert via
    ``entity_registry.async_get(...).entity_category``, not via
    ``state.attributes`` (which omits the field when it is ``None``).
    """
    await _setup_integration(hass, config_entry_with_vehicles)
    fake_stream.fire_frame(
        MOCK_VEHICLE_ID, Telemetry(**{metric.value: build_metric_value(value)})
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
    "entity_registry_enabled_by_default", "mock_abrp_client", "fake_stream"
)
async def test_calibrated_ref_cons_renamed_to_short_form(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    fake_stream: Any,
) -> None:
    """The calibrated ref cons sensor's friendly name translates to the short form.

    The device card width is dominated by the longest sensor name; the
    full ``Calibrated reference consumption`` wraps or truncates on
    narrow viewports. The translation string shortens to
    ``Calibrated ref cons``. Asserted via the registry's
    ``original_name`` — the resolved translation at registration time,
    independent of friendly-name composition with the device prefix.
    """
    await _setup_integration(hass, config_entry_with_vehicles)
    fake_stream.fire_frame(
        MOCK_VEHICLE_ID, Telemetry(calibrated_ref_cons=build_metric_value(175.0))
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
    assert entry.original_name == "Calibrated ref cons"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "fake_stream")
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

    _set_two_make_displays(mock_abrp_client)
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
    "entity_registry_enabled_by_default", "mock_abrp_client", "fake_stream"
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


# A single ``SensorDeviceClass.ENUM`` sensor surfacing the categorical
# ``charging_state`` metric. The library emits a typed ``ChargingState``
# member; the integration maps it to its HA option string
# (charging_ac / charging_dc / charging_unknown / not_charging /
# plugged_in) via ``CHARGING_STATE_OPTIONS``. Shares the generic
# telemetry-sensor base, so lazy create + restore + ``last_reported_at`` /
# ``provider`` attributes come for free.


@pytest.mark.parametrize(
    ("charging_state", "expected_option"),
    [
        pytest.param(ChargingState.CHARGING_AC, "charging_ac", id="charging_ac"),
        pytest.param(ChargingState.CHARGING_DC, "charging_dc", id="charging_dc"),
        pytest.param(
            ChargingState.CHARGING_UNKNOWN, "charging_unknown", id="charging_unknown"
        ),
        pytest.param(ChargingState.NOT_CHARGING, "not_charging", id="not_charging"),
        pytest.param(ChargingState.PLUGGED_IN, "plugged_in", id="plugged_in"),
    ],
)
def test_charging_state_options_map_every_member(
    charging_state: ChargingState,
    expected_option: str,
) -> None:
    """Every ``ChargingState`` member maps to its lowercase HA option key.

    ``CHARGING_STATE_OPTIONS`` is the HA-owned, total-over-``ChargingState``
    map the enum sensor reads to coerce a typed library member to a valid
    ``options`` string. Pairs with the cross-pin guard (which proves the
    option set stays in sync with the entity description ``options`` and the
    ``strings.json`` / ``icons.json`` per-state maps).
    """
    assert CHARGING_STATE_OPTIONS[charging_state] == expected_option


@pytest.mark.parametrize(
    ("charging_state", "expected_option"),
    [
        pytest.param(ChargingState.CHARGING_AC, "charging_ac", id="charging_ac"),
        pytest.param(ChargingState.NOT_CHARGING, "not_charging", id="not_charging"),
        pytest.param(ChargingState.PLUGGED_IN, "plugged_in", id="plugged_in"),
    ],
)
@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_abrp_client", "fake_stream"
)
async def test_charging_state_lazy_create_via_dispatcher(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    fake_stream: Any,
    charging_state: ChargingState,
    expected_option: str,
) -> None:
    """First ``charging_state`` frame after setup lazily creates the enum sensor.

    Routes the frame through the stream's ``on_update`` *after* the platform
    has registered its presence predicates, exercising the dispatcher
    ``_on_new_metric`` path (the primary path for an event-driven field
    rarely present in the seed snapshot). The entity must be absent before
    the frame and surface the mapped lowercase option afterwards.
    """
    await _setup_integration(hass, config_entry_with_vehicles)

    # Negation: no charging_state frame yet → no entity.
    assert hass.states.get(CHARGING_STATE_ENTITY_ID) is None

    fake_stream.fire_frame(
        MOCK_VEHICLE_ID,
        Telemetry(charging_state=build_metric_value(charging_state)),
    )
    await hass.async_block_till_done()

    state = hass.states.get(CHARGING_STATE_ENTITY_ID)
    assert state is not None
    assert state.state == expected_option


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_abrp_client", "fake_stream"
)
async def test_charging_state_registry_shape(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    fake_stream: Any,
) -> None:
    """The enum sensor is ENUM device_class, the 5 options, and no state_class.

    Pins the static description shape (mirrors the ``battery_capacity``
    static-pin precedent for ``state_class is None`` so a future
    copy-paste from a numeric sensor can't attach one). ENUM sensors carry
    no unit and are LTS-ineligible.
    """
    description = SENSORS_BY_METRIC[Metric.CHARGING_STATE]
    assert description.device_class is SensorDeviceClass.ENUM
    assert description.options == list(CHARGING_STATE_OPTIONS.values())
    assert description.state_class is None
    assert description.native_unit_of_measurement is None

    await _setup_integration(hass, config_entry_with_vehicles)
    fake_stream.fire_frame(
        MOCK_VEHICLE_ID,
        Telemetry(charging_state=build_metric_value(ChargingState.CHARGING_AC)),
    )
    await hass.async_block_till_done()

    state = hass.states.get(CHARGING_STATE_ENTITY_ID)
    assert state is not None
    assert state.attributes["device_class"] == SensorDeviceClass.ENUM
    assert state.attributes["options"] == list(CHARGING_STATE_OPTIONS.values())
    assert "state_class" not in state.attributes
    assert "unit_of_measurement" not in state.attributes


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_abrp_client", "fake_stream"
)
async def test_charging_state_provider_and_stamp_attributes(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    fake_stream: Any,
) -> None:
    """The enum sensor surfaces ``provider`` + ``last_reported_at`` like numerics.

    The generic base composes both attributes for the enum sensor with no
    enum-specific override — a live frame carrying a provider stamps both
    the per-metric ``last_provider`` and ``last_reported_at`` maps, and the
    entity surfaces them. ``last_reported_at`` is the RECEIPT time (stamped
    by the coordinator), so freezing time around the push pins it.
    """
    await _setup_integration(hass, config_entry_with_vehicles)

    stamp = datetime(2026, 5, 24, 12, 0, 0, tzinfo=UTC)
    with freeze_time(stamp):
        fake_stream.fire_frame(
            MOCK_VEHICLE_ID,
            Telemetry(
                charging_state=build_metric_value(
                    ChargingState.CHARGING_DC, provider="RIVIAN_STREAM"
                )
            ),
        )
        await hass.async_block_till_done()

    state = hass.states.get(CHARGING_STATE_ENTITY_ID)
    assert state is not None
    assert state.state == "charging_dc"
    assert state.attributes.get("provider") == "RIVIAN_STREAM"
    assert state.attributes.get("last_reported_at") == stamp


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

    The TelemetryStream is faked by the ``fake_stream`` fixture, so this helper
    drives a real ``async_setup`` without opening an SSE connection.
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
@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_charging_state_restore_native_value(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    restored_value: str,
    expected_state: str,
) -> None:
    """Restored enum state survives restart only when it is a valid option.

    Four trajectories share the restore-setup → assert-state structure:

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

    No seed is configured for the vehicle (the seed table defaults to an
    empty dict), so the entity is re-created purely from the pre-seeded
    registry row, exercising the restore path without a live wake frame.
    """
    await _charging_restart_setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        restored_states=[_charging_restored_state(native_value=restored_value)],
    )

    state = hass.states.get(CHARGING_STATE_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_charging_state_restores_provider_and_stamp(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Restored ``provider`` + ``last_reported_at`` surface on the enum sensor.

    The enum sensor inherits the shared base's stamp/provider restore, so a
    parked vehicle keeps both attributes across restart without a wake frame.
    """
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


def test_charging_state_options_cross_pinned() -> None:
    """The truth stays in sync across every copy.

    Three copies of the closed enum must agree, or a drift goes RED:

    1. ``CHARGING_STATE_OPTIONS`` keys cover every library ``ChargingState``
       member (the map must be total so ``native_value`` always resolves to
       a valid option).
    2. ``CHARGING_STATE_OPTIONS`` values ↔ the enum entity description's
       ``options`` list.
    3. + 4. ``CHARGING_STATE_OPTIONS`` values ↔ the
       ``entity.sensor.charging_state.state`` keyset in BOTH ``strings.json``
       and ``icons.json`` (a missing label / icon silently renders the raw
       option key in the UI). The source files are read directly (not the
       generated ``translations/en.json``).
    """
    assert set(CHARGING_STATE_OPTIONS) == set(ChargingState)

    description = SENSORS_BY_METRIC[Metric.CHARGING_STATE]
    assert description.options is not None
    assert set(CHARGING_STATE_OPTIONS.values()) == set(description.options)

    strings = json.loads(
        (_INTEGRATION_DIR / "strings.json").read_text(encoding="utf-8")
    )
    icons = json.loads((_INTEGRATION_DIR / "icons.json").read_text(encoding="utf-8"))
    strings_states = strings["entity"]["sensor"]["charging_state"]["state"]
    icons_states = icons["entity"]["sensor"]["charging_state"]["state"]
    assert set(CHARGING_STATE_OPTIONS.values()) == set(strings_states)
    assert set(CHARGING_STATE_OPTIONS.values()) == set(icons_states)
