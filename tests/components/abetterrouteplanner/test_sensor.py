"""Tests for the A Better Routeplanner sensor platform."""

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

from aioabrp import (
    AbrpVehicle,
    ChargingState,
    ConnectionEvent,
    ConnectionState,
    Metric,
    Telemetry,
    VehicleModelDisplay,
)
from freezegun import freeze_time
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import abetterrouteplanner as abrp_module
from homeassistant.components.abetterrouteplanner.const import DOMAIN
from homeassistant.components.abetterrouteplanner.sensor import (
    CHARGING_STATE_OPTIONS,
    SENSORS,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import (
    MOCK_VEHICLE_ID,
    MOCK_VEHICLE_ID_2,
    MOCK_VEHICLE_MODEL,
    MOCK_VEHICLE_NAME,
    SENSOR_TEST_SUB,
    build_metric_value,
    build_vehicle_model_display,
)

from tests.common import MockConfigEntry, snapshot_platform

SOC_ENTITY_ID = "sensor.rivian_r2_2027_standard_long_range_soc"
POWER_ENTITY_ID = "sensor.rivian_r2_2027_standard_long_range_power"
VOLTAGE_ENTITY_ID = "sensor.rivian_r2_2027_standard_long_range_voltage"
CHARGING_STATE_ENTITY_ID = "sensor.rivian_r2_2027_standard_long_range_charging_state"
CHARGING_STATE_UNIQUE_ID = f"{SENSOR_TEST_SUB}_{MOCK_VEHICLE_ID}_charging_state"

# The source files, not the generated ``translations/en.json``, so a missing
# label or icon fails loudly.
_INTEGRATION_DIR = Path(abrp_module.__file__).parent


def _description_for(metric: Metric) -> Any:
    """Return the sensor description bound to a metric."""
    return next(description for description in SENSORS if description.metric is metric)


async def _setup_integration(
    hass: HomeAssistant, entry: MockConfigEntry
) -> MockConfigEntry:
    """Register the integration's OAuth implementation and set up the entry.

    Callers with a non-empty garage must also request ``fake_stream``, or a real
    TelemetryStream opens an SSE connection.
    """
    assert await async_setup_component(hass, "auth", {})
    assert await async_setup_component(hass, DOMAIN, {})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.mark.parametrize(
    "vehicle_id",
    [
        pytest.param(MOCK_VEHICLE_ID, id="first_garage_vehicle"),
        pytest.param(MOCK_VEHICLE_ID_2, id="second_garage_vehicle"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_abrp_client")
async def test_every_garage_vehicle_present_in_registries(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    fake_stream: Any,
    vehicle_id: int,
) -> None:
    """Every vehicle in the garage gets a device and entities, with no opt-in step."""
    await _setup_integration(hass, config_entry_with_vehicles)

    # Read the sub off the fixture so this survives a parametrized unique_id.
    scope = config_entry_with_vehicles.unique_id
    assert (
        device_registry.async_get_device(
            identifiers={(DOMAIN, f"{scope}_{vehicle_id}")}
        )
        is not None
    )

    # Entities are created lazily, so drive a frame for this vehicle.
    fake_stream.fire_frame(vehicle_id, Telemetry(soc=build_metric_value(85.0)))
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{scope}_{vehicle_id}_soc"
        )
        is not None
    )


async def test_empty_garage_creates_no_devices_or_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_abrp_client: AsyncMock,
) -> None:
    """An empty garage loads the entry but registers nothing."""
    mock_abrp_client.return_value = []

    await _setup_integration(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED
    assert not er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    assert not dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)


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
    """Entity registry + states snapshot for the full per-vehicle metric set."""
    await _setup_integration(hass, config_entry_with_vehicles)

    # Every metric in one frame so the snapshot captures rendered states, with
    # time frozen so the receipt-stamped ``last_reported_at`` is deterministic.
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
    """SoC surfaces the typed PERCENT ``MetricValue.value`` with one decimal."""
    await _setup_integration(hass, config_entry_with_vehicles)

    fake_stream.fire_frame(MOCK_VEHICLE_ID, Telemetry(soc=build_metric_value(85.7)))
    await hass.async_block_till_done()

    state = hass.states.get(SOC_ENTITY_ID)
    assert state is not None
    assert state.state == "85.7"


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_abrp_client", "fake_stream"
)
async def test_available_follows_native_value(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    fake_stream: Any,
) -> None:
    """``available`` tracks ``native_value is not None``."""
    await _setup_integration(hass, config_entry_with_vehicles)

    fake_stream.fire_frame(
        MOCK_VEHICLE_ID, Telemetry(power=build_metric_value(12000.0))
    )
    await hass.async_block_till_done()

    state = hass.states.get(POWER_ENTITY_ID)
    assert state is not None
    assert state.state != "unavailable"
    assert state.state == "12000.0"


# The "range_range" doubling below is the device name meeting translation_key.


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
    """Range sensor surfaces the meters ``MetricValue.value`` rendered in km."""
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
    """Battery Temperature sensor surfaces the Celsius ``MetricValue.value``."""
    await _setup_integration(hass, config_entry_with_vehicles)

    fake_stream.fire_frame(
        MOCK_VEHICLE_ID, Telemetry(battery_temperature=build_metric_value(temp_c))
    )
    await hass.async_block_till_done()

    state = hass.states.get(BATTERY_TEMP_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


def _make_vehicle(
    *,
    vehicle_id: int = MOCK_VEHICLE_ID,
    name: str | None = "Rivian R2 2027 Standard Long Range",
    vehicle_model: str = MOCK_VEHICLE_MODEL,
    paint: str | None = "WHITE",
) -> AbrpVehicle:
    """Build an AbrpVehicle from its four identity fields."""
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
    """Return the entity_id for a per-vehicle sensor, or ``None`` if absent."""
    return entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{_scope(entry, vehicle_id)}_{translation_key}"
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "fake_stream")
async def test_device_info_name_falls_back_to_typecode_when_unnamed(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    mock_abrp_client: AsyncMock,
) -> None:
    """``DeviceInfo.name`` falls back to the raw typecode for an unnamed vehicle."""
    mock_abrp_client.return_value = [_make_vehicle(name=None)]

    await _setup_integration(hass, config_entry_with_vehicles)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, _scope(config_entry_with_vehicles, MOCK_VEHICLE_ID))}
    )
    assert device is not None
    assert device.name == MOCK_VEHICLE_MODEL


# Two makes: a single-make setup can't tell per-vehicle binding from a
# hard-coded first make.
_POLESTAR_VEHICLE_MODEL = "polestar:2:24:bev:awd"


def _set_two_make_displays(
    mock_abrp_client: AsyncMock,
) -> dict[int, VehicleModelDisplay]:
    """Register display fixtures for the two distinct-make vehicles."""
    displays = {
        MOCK_VEHICLE_ID: build_vehicle_model_display(
            manufacturer="Rivian",
            model="R2",
            years="2026",
            title="",
            start_year=2026,
            end_year=None,
        ),
        MOCK_VEHICLE_ID_2: build_vehicle_model_display(
            manufacturer="Polestar",
            model="2",
            years="2024",
            title="",
            start_year=2024,
            end_year=None,
        ),
    }
    mock_abrp_client.display_responses[MOCK_VEHICLE_MODEL] = displays[MOCK_VEHICLE_ID]
    mock_abrp_client.display_responses[_POLESTAR_VEHICLE_MODEL] = displays[
        MOCK_VEHICLE_ID_2
    ]
    return displays


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
    """Four telemetry sensors no longer carry ``EntityCategory.DIAGNOSTIC``."""
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
    """The calibrated ref cons sensor's friendly name translates to the short form."""
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
    config_entry_with_vehicles: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    mock_abrp_client: AsyncMock,
) -> None:
    """Each garage vehicle's device exists with full metadata after setup."""
    polestar_name = "Polestar 2 Long Range"
    mock_abrp_client.return_value = [
        _make_vehicle(),
        _make_vehicle(
            vehicle_id=MOCK_VEHICLE_ID_2,
            name=polestar_name,
            vehicle_model=_POLESTAR_VEHICLE_MODEL,
        ),
    ]
    entry = config_entry_with_vehicles

    displays = _set_two_make_displays(mock_abrp_client)
    await _setup_integration(hass, entry)

    expected_names = {
        MOCK_VEHICLE_ID: MOCK_VEHICLE_NAME,
        MOCK_VEHICLE_ID_2: polestar_name,
    }
    for vehicle_id, display in displays.items():
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, f"{SENSOR_TEST_SUB}_{vehicle_id}")}
        )
        assert device is not None
        assert device.manufacturer == display.manufacturer
        # ``model_name`` drops the make, which has its own field; the label's
        # own composition rules are the library's contract.
        assert device.model == display.model_name
        assert device.name == expected_names[vehicle_id]
        assert device.configuration_url == (
            f"https://abetterrouteplanner.com/?vehicle_id={vehicle_id}"
        )


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_abrp_client", "fake_stream"
)
async def test_no_type_code_entity_created(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """No entity with a ``_type_code`` unique-id suffix is registered."""
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
    """Every ``ChargingState`` member maps to its lowercase HA option key."""
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
async def test_charging_state_lazy_create_on_first_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    fake_stream: Any,
    charging_state: ChargingState,
    expected_option: str,
) -> None:
    """First ``charging_state`` frame after setup lazily creates the enum sensor."""
    await _setup_integration(hass, config_entry_with_vehicles)

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
    """The enum sensor is ENUM device_class, the 5 options, and no state_class."""
    description = _description_for(Metric.CHARGING_STATE)
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
    """The enum sensor surfaces ``provider`` + ``last_reported_at`` like numerics."""
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


def test_charging_state_options_cross_pinned() -> None:
    """Option map matches ChargingState, the description options, strings and icons."""
    assert set(CHARGING_STATE_OPTIONS) == set(ChargingState)

    description = _description_for(Metric.CHARGING_STATE)
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


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_abrp_client", "fake_stream"
)
async def test_terminal_auth_failure_makes_sensors_unavailable(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    fake_stream: Any,
) -> None:
    """A value that nothing can refresh stops being reported."""
    await _setup_integration(hass, config_entry_with_vehicles)

    fake_stream.fire_frame(
        MOCK_VEHICLE_ID, Telemetry(power=build_metric_value(12000.0))
    )
    await hass.async_block_till_done()
    assert hass.states.get(POWER_ENTITY_ID).state == "12000.0"

    fake_stream.fire_connection(ConnectionEvent(ConnectionState.AUTH_FAILED, "401"))
    await hass.async_block_till_done()
    assert hass.states.get(POWER_ENTITY_ID).state == "unavailable"
