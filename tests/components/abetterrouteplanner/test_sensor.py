"""Tests for the A Better Routeplanner sensor platform."""

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

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
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .conftest import (
    MOCK_VEHICLE_ID,
    MOCK_VEHICLE_ID_2,
    MOCK_VEHICLE_MODEL,
    MOCK_VEHICLE_NAME,
    SENSOR_TEST_SUB,
    build_metric_value,
    build_vehicle_model_display,
    fire_connection,
    fire_frame,
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
    mock_telemetry_stream: MagicMock,
    vehicle_id: int,
) -> None:
    """Every vehicle in the garage gets a device and entities, with no opt-in step."""
    await setup_integration(hass, config_entry_with_vehicles)

    # Read the sub off the fixture so this survives a parametrized unique_id.
    scope = config_entry_with_vehicles.unique_id
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{scope}_{vehicle_id}"), config_entry_with_vehicles.entry_id
        )
        is not None
    )

    # Entities are created lazily, so drive a frame for this vehicle.
    fire_frame(
        mock_telemetry_stream, vehicle_id, Telemetry(soc=build_metric_value(85.0))
    )
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

    await setup_integration(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED
    assert not er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    assert not dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_abrp_client", "mock_telemetry_stream"
)
async def test_telemetry_sensors_snapshot(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_telemetry_stream: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Entity registry + states snapshot for the full per-vehicle metric set."""
    await setup_integration(hass, config_entry_with_vehicles)

    # Every metric in one frame so the snapshot captures rendered states, with
    # time frozen so the receipt-stamped ``last_reported_at`` is deterministic.
    with freeze_time("2026-05-24T12:00:00+00:00"):
        fire_frame(
            mock_telemetry_stream,
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
    "entity_registry_enabled_by_default", "mock_abrp_client", "mock_telemetry_stream"
)
async def test_soc_native_value_is_percent(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_telemetry_stream: MagicMock,
) -> None:
    """SoC surfaces the typed PERCENT ``MetricValue.value`` with one decimal."""
    await setup_integration(hass, config_entry_with_vehicles)

    fire_frame(
        mock_telemetry_stream, MOCK_VEHICLE_ID, Telemetry(soc=build_metric_value(85.7))
    )
    await hass.async_block_till_done()

    state = hass.states.get(SOC_ENTITY_ID)
    assert state is not None
    assert state.state == "85.7"


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_abrp_client", "mock_telemetry_stream"
)
async def test_available_follows_native_value(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_telemetry_stream: MagicMock,
) -> None:
    """``available`` tracks ``native_value is not None``."""
    await setup_integration(hass, config_entry_with_vehicles)

    fire_frame(
        mock_telemetry_stream,
        MOCK_VEHICLE_ID,
        Telemetry(power=build_metric_value(12000.0)),
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
    "entity_registry_enabled_by_default", "mock_abrp_client", "mock_telemetry_stream"
)
async def test_range_sensor_state(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_telemetry_stream: MagicMock,
    range_m: float,
    expected_state: str,
) -> None:
    """Range sensor surfaces the meters ``MetricValue.value`` rendered in km."""
    await setup_integration(hass, config_entry_with_vehicles)

    fire_frame(
        mock_telemetry_stream,
        MOCK_VEHICLE_ID,
        Telemetry(range=build_metric_value(range_m)),
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
    "entity_registry_enabled_by_default", "mock_abrp_client", "mock_telemetry_stream"
)
async def test_battery_temperature_sensor_state(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_telemetry_stream: MagicMock,
    temp_c: float,
    expected_state: str,
) -> None:
    """Battery Temperature sensor surfaces the Celsius ``MetricValue.value``."""
    await setup_integration(hass, config_entry_with_vehicles)

    fire_frame(
        mock_telemetry_stream,
        MOCK_VEHICLE_ID,
        Telemetry(battery_temperature=build_metric_value(temp_c)),
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


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_telemetry_stream")
async def test_device_info_name_falls_back_to_typecode_when_unnamed(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    mock_abrp_client: AsyncMock,
) -> None:
    """``DeviceInfo.name`` falls back to the raw typecode for an unnamed vehicle."""
    mock_abrp_client.return_value = [_make_vehicle(name=None)]

    await setup_integration(hass, config_entry_with_vehicles)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, _scope(config_entry_with_vehicles, MOCK_VEHICLE_ID)),
        config_entry_with_vehicles.entry_id,
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
    "entity_registry_enabled_by_default", "mock_abrp_client", "mock_telemetry_stream"
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
async def test_telemetry_sensors_have_no_entity_category(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_telemetry_stream: MagicMock,
    sensor_key: str,
    metric: Metric,
    value: float,
) -> None:
    """These four sensors are primary vehicle data, not diagnostics."""
    await setup_integration(hass, config_entry_with_vehicles)
    fire_frame(
        mock_telemetry_stream,
        MOCK_VEHICLE_ID,
        Telemetry(**{metric.value: build_metric_value(value)}),
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
    "entity_registry_enabled_by_default", "mock_abrp_client", "mock_telemetry_stream"
)
async def test_calibrated_ref_cons_uses_short_display_name(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_telemetry_stream: MagicMock,
) -> None:
    """The calibrated ref cons sensor's friendly name translates to the short form."""
    await setup_integration(hass, config_entry_with_vehicles)
    fire_frame(
        mock_telemetry_stream,
        MOCK_VEHICLE_ID,
        Telemetry(calibrated_ref_cons=build_metric_value(175.0)),
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


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_telemetry_stream")
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
    await setup_integration(hass, entry)

    expected_names = {
        MOCK_VEHICLE_ID: MOCK_VEHICLE_NAME,
        MOCK_VEHICLE_ID_2: polestar_name,
    }
    for vehicle_id, display in displays.items():
        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{SENSOR_TEST_SUB}_{vehicle_id}"), entry.entry_id
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
    "entity_registry_enabled_by_default", "mock_abrp_client", "mock_telemetry_stream"
)
async def test_no_type_code_entity_created(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """No entity with a ``_type_code`` unique-id suffix is registered."""
    await setup_integration(hass, config_entry_with_vehicles)

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
        pytest.param(ChargingState.NOT_CHARGING, "not_charging", id="not_charging"),
        pytest.param(ChargingState.PLUGGED_IN, "plugged_in", id="plugged_in"),
    ],
)
@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_abrp_client", "mock_telemetry_stream"
)
async def test_charging_state_lazy_create_on_first_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_telemetry_stream: MagicMock,
    charging_state: ChargingState,
    expected_option: str,
) -> None:
    """First ``charging_state`` frame after setup lazily creates the enum sensor."""
    await setup_integration(hass, config_entry_with_vehicles)

    assert hass.states.get(CHARGING_STATE_ENTITY_ID) is None

    fire_frame(
        mock_telemetry_stream,
        MOCK_VEHICLE_ID,
        Telemetry(charging_state=build_metric_value(charging_state)),
    )
    await hass.async_block_till_done()

    state = hass.states.get(CHARGING_STATE_ENTITY_ID)
    assert state is not None
    assert state.state == expected_option


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_abrp_client", "mock_telemetry_stream"
)
async def test_charging_state_provider_and_stamp_attributes(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_telemetry_stream: MagicMock,
) -> None:
    """The enum sensor surfaces ``provider`` + ``last_reported_at`` like numerics."""
    await setup_integration(hass, config_entry_with_vehicles)

    stamp = datetime(2026, 5, 24, 12, 0, 0, tzinfo=UTC)
    with freeze_time(stamp):
        fire_frame(
            mock_telemetry_stream,
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
    "entity_registry_enabled_by_default", "mock_abrp_client", "mock_telemetry_stream"
)
async def test_availability_follows_stream_auth_not_connection(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_telemetry_stream: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Idle disconnects keep values; a terminal auth failure hides them until reconnect."""
    await setup_integration(hass, config_entry_with_vehicles)
    fire_frame(
        mock_telemetry_stream,
        MOCK_VEHICLE_ID,
        Telemetry(power=build_metric_value(12000.0)),
    )
    await hass.async_block_till_done()

    fire_connection(
        mock_telemetry_stream,
        ConnectionEvent(ConnectionState.DISCONNECTED, "idle close"),
    )
    await hass.async_block_till_done()
    assert hass.states.get(POWER_ENTITY_ID).state == "12000.0"

    fire_connection(
        mock_telemetry_stream, ConnectionEvent(ConnectionState.AUTH_FAILED, "401")
    )
    await hass.async_block_till_done()
    assert hass.states.get(POWER_ENTITY_ID).state == "unavailable"
    assert "auth failed" in caplog.text
    assert not hass.config_entries.flow.async_progress()

    fire_connection(
        mock_telemetry_stream,
        ConnectionEvent(ConnectionState.DISCONNECTED, "idle close"),
    )
    await hass.async_block_till_done()
    assert hass.states.get(POWER_ENTITY_ID).state == "unavailable"

    fire_connection(mock_telemetry_stream, ConnectionEvent(ConnectionState.CONNECTED))
    await hass.async_block_till_done()
    assert hass.states.get(POWER_ENTITY_ID).state == "12000.0"


VOLTAGE_ENTITY_ID_2 = "sensor.rivian_r1s_2024_quad_max_voltage"


# Not in the mocked garage, so the stream never subscribes to it.
_ABSENT_VEHICLE_ID = 999999999999


def _unique_id_lookup(
    entity_registry: er.EntityRegistry, vehicle_id: int, key: str
) -> str | None:
    """Look up an entity_id via ``unique_id`` to decouple from strings.json slugs."""
    return entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SENSOR_TEST_SUB}_{vehicle_id}_{key}"
    )


@pytest.mark.usefixtures("mock_abrp_client")
async def test_stream_only_metric_creates_entity(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    mock_telemetry_stream: MagicMock,
) -> None:
    """The seed is empty; a power frame arrives over the stream."""

    await setup_integration(hass, config_entry_with_vehicles)

    assert entity_registry.async_get(POWER_ENTITY_ID) is None

    fire_frame(
        mock_telemetry_stream,
        MOCK_VEHICLE_ID,
        Telemetry(power=build_metric_value(1234.0)),
    )
    await hass.async_block_till_done()

    state = hass.states.get(POWER_ENTITY_ID)
    assert state is not None
    assert state.state == "1234.0"

    assert entity_registry.async_get(SOC_ENTITY_ID) is None
    assert entity_registry.async_get(VOLTAGE_ENTITY_ID) is None


@pytest.mark.usefixtures("mock_abrp_client")
async def test_post_setup_frame_creates_entity(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    mock_telemetry_stream: MagicMock,
) -> None:
    """The seed is empty; voltage arrives only after setup completes."""

    await setup_integration(hass, config_entry_with_vehicles)

    assert entity_registry.async_get(SOC_ENTITY_ID) is None
    assert entity_registry.async_get(POWER_ENTITY_ID) is None
    assert entity_registry.async_get(VOLTAGE_ENTITY_ID) is None

    fire_frame(
        mock_telemetry_stream,
        MOCK_VEHICLE_ID,
        Telemetry(voltage=build_metric_value(400.0)),
    )
    await hass.async_block_till_done()

    assert entity_registry.async_get(VOLTAGE_ENTITY_ID) is not None
    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.state == "400.0"

    assert entity_registry.async_get(SOC_ENTITY_ID) is None
    assert entity_registry.async_get(POWER_ENTITY_ID) is None

    # Pin via the registry: ``state.attributes`` never carries the category.
    registry_entry = entity_registry.async_get(VOLTAGE_ENTITY_ID)
    assert registry_entry is not None
    assert registry_entry.entity_category is None


@pytest.mark.usefixtures("mock_abrp_client")
async def test_lazy_create_idempotent_on_repeated_frames(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    mock_telemetry_stream: MagicMock,
) -> None:
    """Two consecutive non-null power frames must create exactly one power entity."""

    await setup_integration(hass, config_entry_with_vehicles)

    assert entity_registry.async_get(POWER_ENTITY_ID) is None

    fire_frame(
        mock_telemetry_stream,
        MOCK_VEHICLE_ID,
        Telemetry(power=build_metric_value(5000.0)),
    )
    await hass.async_block_till_done()

    fire_frame(
        mock_telemetry_stream,
        MOCK_VEHICLE_ID,
        Telemetry(power=build_metric_value(6000.0)),
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
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    mock_telemetry_stream: MagicMock,
    active_vehicle_id: int,
    expected_entity_id: str,
    absent_entity_id: str,
) -> None:
    """Voltage arriving for vehicle A must not create a voltage entity for vehicle B."""
    entry = config_entry_with_vehicles

    await setup_integration(hass, entry)

    assert entity_registry.async_get(absent_entity_id) is None

    fire_frame(
        mock_telemetry_stream,
        active_vehicle_id,
        Telemetry(voltage=build_metric_value(400.0)),
    )
    await hass.async_block_till_done()

    assert entity_registry.async_get(expected_entity_id) is not None
    assert entity_registry.async_get(absent_entity_id) is None


@pytest.mark.usefixtures("mock_abrp_client", "mock_telemetry_stream")
async def test_absent_metric_entities_not_created(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
) -> None:
    """An empty seed with no stream frames must produce zero telemetry entities."""

    await setup_integration(hass, config_entry_with_vehicles)

    assert entity_registry.async_get(SOC_ENTITY_ID) is None
    assert entity_registry.async_get(POWER_ENTITY_ID) is None
    assert entity_registry.async_get(VOLTAGE_ENTITY_ID) is None


@pytest.mark.usefixtures("mock_abrp_client")
async def test_soe_sensor_lazy_creates_on_first_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    mock_telemetry_stream: MagicMock,
) -> None:
    """An ``soe`` frame lazy-creates the SoE sensor; native Wh, display kWh."""

    await setup_integration(hass, config_entry_with_vehicles)

    assert _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "soe") is None

    fire_frame(
        mock_telemetry_stream,
        MOCK_VEHICLE_ID,
        Telemetry(soe=build_metric_value(75000.0)),
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


@pytest.mark.usefixtures("mock_abrp_client")
async def test_odometer_sensor_lazy_creates_on_first_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    mock_telemetry_stream: MagicMock,
) -> None:
    """An ``odometer`` frame lazy-creates the odometer sensor; native m, display km."""

    await setup_integration(hass, config_entry_with_vehicles)

    assert _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "odometer") is None

    fire_frame(
        mock_telemetry_stream,
        MOCK_VEHICLE_ID,
        Telemetry(odometer=build_metric_value(123456.0)),
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
    mock_telemetry_stream: MagicMock,
) -> None:
    """A ``calibrated_ref_cons`` frame lazy-creates the ref-consumption sensor."""

    await setup_integration(hass, config_entry_with_vehicles)

    assert (
        _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "calibrated_ref_cons")
        is None
    )

    fire_frame(
        mock_telemetry_stream,
        MOCK_VEHICLE_ID,
        Telemetry(calibrated_ref_cons=build_metric_value(175.0)),
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

    registry_entry = entity_registry.async_get(entity_id)
    assert registry_entry is not None
    assert registry_entry.entity_category is None


@pytest.mark.usefixtures("mock_abrp_client")
async def test_battery_capacity_sensor_lazy_creates_static(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    mock_telemetry_stream: MagicMock,
) -> None:
    """A ``battery_capacity`` frame lazy-creates the capacity sensor as STATIC."""

    await setup_integration(hass, config_entry_with_vehicles)

    assert (
        _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "battery_capacity") is None
    )

    fire_frame(
        mock_telemetry_stream,
        MOCK_VEHICLE_ID,
        Telemetry(battery_capacity=build_metric_value(75000.0)),
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

    registry_entry = entity_registry.async_get(entity_id)
    assert registry_entry is not None
    assert registry_entry.entity_category is None


@pytest.mark.usefixtures("mock_abrp_client")
async def test_soh_sensor_lazy_creates_on_first_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    mock_telemetry_stream: MagicMock,
) -> None:
    """A ``soh`` frame lazy-creates the State-of-Health sensor (percent)."""

    await setup_integration(hass, config_entry_with_vehicles)

    assert _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "soh") is None

    fire_frame(
        mock_telemetry_stream, MOCK_VEHICLE_ID, Telemetry(soh=build_metric_value(92.0))
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

    registry_entry = entity_registry.async_get(entity_id)
    assert registry_entry is not None
    assert registry_entry.entity_category is None


@pytest.mark.usefixtures("mock_abrp_client")
async def test_battery_temperature_sensor_stays_primary_category(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    mock_telemetry_stream: MagicMock,
) -> None:
    """Battery Temperature stays primary (``entity_category is None``)."""

    await setup_integration(hass, config_entry_with_vehicles)

    assert (
        _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "battery_temperature")
        is None
    )

    fire_frame(
        mock_telemetry_stream,
        MOCK_VEHICLE_ID,
        Telemetry(battery_temperature=build_metric_value(22.5)),
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
    mock_telemetry_stream: MagicMock,
) -> None:
    """A post-recalibration SoH overshoot (> 100%) surfaces uncapped."""

    await setup_integration(hass, config_entry_with_vehicles)

    fire_frame(
        mock_telemetry_stream, MOCK_VEHICLE_ID, Telemetry(soh=build_metric_value(105.0))
    )
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
    mock_telemetry_stream: MagicMock,
) -> None:
    """A capacity recalibration jump is reflected in ``state.state``."""

    await setup_integration(hass, config_entry_with_vehicles)

    fire_frame(
        mock_telemetry_stream,
        MOCK_VEHICLE_ID,
        Telemetry(battery_capacity=build_metric_value(75000.0)),
    )
    await hass.async_block_till_done()

    entity_id = _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "battery_capacity")
    assert entity_id is not None
    first_state = hass.states.get(entity_id)
    assert first_state is not None
    assert first_state.state == "75.0"

    fire_frame(
        mock_telemetry_stream,
        MOCK_VEHICLE_ID,
        Telemetry(battery_capacity=build_metric_value(74500.0)),
    )
    await hass.async_block_till_done()

    second_state = hass.states.get(entity_id)
    assert second_state is not None
    assert second_state.state == "74.5"


@pytest.mark.usefixtures("mock_abrp_client")
async def test_new_sensor_multi_vehicle_isolation(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    mock_telemetry_stream: MagicMock,
) -> None:
    """A metric frame for vehicle A must not create the entity on vehicle B."""
    entry = config_entry_with_vehicles

    await setup_integration(hass, entry)

    fire_frame(
        mock_telemetry_stream,
        MOCK_VEHICLE_ID,
        Telemetry(calibrated_ref_cons=build_metric_value(175.0)),
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

    # A frame for an id outside the garage must not mint an entity either.
    fire_frame(
        mock_telemetry_stream,
        _ABSENT_VEHICLE_ID,
        Telemetry(soc=build_metric_value(50.0)),
    )
    await hass.async_block_till_done()

    assert _unique_id_lookup(entity_registry, _ABSENT_VEHICLE_ID, "soc") is None


PROVIDER = "RIVIAN_STREAM"

# Object-id stem matching the mock vehicle's name, so a preseeded registry row
# fixes the entity_id instead of leaving it to the auto-slug.
_OBJECT_ID_STEM = "rivian_r2_2027_standard_long_range"


def _fire_voltage(
    mock_telemetry_stream: MagicMock, voltage: float, *, provider: str | None = None
) -> None:
    """Drive a single-voltage live frame through the fake telemetry stream."""
    fire_frame(
        mock_telemetry_stream,
        MOCK_VEHICLE_ID,
        Telemetry(voltage=build_metric_value(voltage, provider=provider)),
    )


async def _setup(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    *,
    entity_registry: er.EntityRegistry | None = None,
    preseed_registry_keys: list[str] | None = None,
) -> None:
    """Set up the integration, optionally preseeding registry rows."""
    hass.set_state(CoreState.not_running)
    entry.add_to_hass(hass)
    if preseed_registry_keys and entity_registry is not None:
        for key in preseed_registry_keys:
            entity_registry.async_get_or_create(
                domain="sensor",
                platform=DOMAIN,
                unique_id=f"{SENSOR_TEST_SUB}_{MOCK_VEHICLE_ID}_{key}",
                config_entry=entry,
                suggested_object_id=f"{_OBJECT_ID_STEM}_{key}",
            )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_abrp_client", "mock_telemetry_stream")
async def test_last_reported_at_stamps_per_metric_not_per_merged_state(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_telemetry_stream: MagicMock,
) -> None:
    """Stamp refreshes only on frames whose batch carries the voltage metric."""

    await _setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_registry_keys=["voltage"],
    )

    t1 = datetime(2026, 5, 24, 10, 0, 0, tzinfo=UTC)
    t2 = datetime(2026, 5, 24, 10, 5, 0, tzinfo=UTC)
    t3 = datetime(2026, 5, 24, 10, 10, 0, tzinfo=UTC)

    with freeze_time(t1):
        fire_frame(
            mock_telemetry_stream,
            MOCK_VEHICLE_ID,
            Telemetry(voltage=build_metric_value(400.0)),
        )
        await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("last_reported_at") == t1

    with freeze_time(t2):
        # This batch carries soc only, so the voltage slot stays untouched.
        fire_frame(
            mock_telemetry_stream,
            MOCK_VEHICLE_ID,
            Telemetry(soc=build_metric_value(50.0)),
        )
        await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("last_reported_at") == t1

    with freeze_time(t3):
        fire_frame(
            mock_telemetry_stream,
            MOCK_VEHICLE_ID,
            Telemetry(voltage=build_metric_value(410.0)),
        )
        await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("last_reported_at") == t3


@pytest.mark.usefixtures("mock_abrp_client", "mock_telemetry_stream")
async def test_wire_time_is_preferred_over_receipt_time(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_telemetry_stream: MagicMock,
) -> None:
    """A reading carrying its own wire time is not stamped with arrival time."""

    await _setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_registry_keys=["voltage"],
    )

    wire = datetime(2026, 5, 20, 8, 0, 0, tzinfo=UTC)
    with freeze_time(datetime(2026, 5, 24, 10, 0, 0, tzinfo=UTC)):
        fire_frame(
            mock_telemetry_stream,
            MOCK_VEHICLE_ID,
            Telemetry(voltage=build_metric_value(400.0, time=wire)),
        )
        await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("last_reported_at") == wire


@pytest.mark.parametrize(
    ("provider", "expected"),
    [
        pytest.param(PROVIDER, PROVIDER, id="provider_surfaces"),
        pytest.param(None, None, id="provider_absent"),
    ],
)
@pytest.mark.usefixtures("mock_abrp_client", "mock_telemetry_stream")
async def test_provider_attribute_follows_the_live_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_telemetry_stream: MagicMock,
    provider: str | None,
    expected: str | None,
) -> None:
    """``provider`` appears only when the frame carries one."""

    await _setup(hass, config_entry_with_vehicles)

    _fire_voltage(mock_telemetry_stream, 400.0, provider=provider)
    await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("provider") == expected


@pytest.mark.usefixtures("mock_abrp_client")
async def test_provider_kept_when_a_frame_omits_it(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_telemetry_stream: MagicMock,
) -> None:
    """A frame without a provider keeps the last one; a new provider replaces it."""
    await _setup(hass, config_entry_with_vehicles)

    for voltage, provider, expected in (
        (400.0, PROVIDER, PROVIDER),
        (410.0, None, PROVIDER),
        (420.0, "APP_LOCATION", "APP_LOCATION"),
    ):
        _fire_voltage(mock_telemetry_stream, voltage, provider=provider)
        await hass.async_block_till_done()
        assert hass.states.get(VOLTAGE_ENTITY_ID).attributes.get("provider") == expected
