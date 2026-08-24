"""Test the Teslemetry sensor platform."""

from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from teslemetry_stream import Signal

from homeassistant.components.teslemetry.const import DOMAIN
from homeassistant.components.teslemetry.coordinator import VEHICLE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
    Platform,
    UnitOfPressure,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_conversion import PressureConverter

from . import assert_entities, assert_entities_alt, setup_platform
from .const import (
    ENERGY_HISTORY_EMPTY,
    LIVE_STATUS,
    METADATA,
    PRODUCTS,
    VEHICLE_DATA_ALT,
)

from tests.common import async_fire_time_changed

# VIN used across the Teslemetry test fixtures.
VEHICLE_VIN = "LRW3F7EK4NC700000"


def _products_with_driver_assist(driver_assist: str) -> dict:
    """Return a products response with the vehicle's driver-assist capability set."""
    products = deepcopy(PRODUCTS)
    products["response"][0]["vehicle_config"]["driver_assist"] = driver_assist
    return products


def _live_status(**overrides: object) -> dict:
    """Return a copy of the live_status document with overrides applied."""
    data = deepcopy(LIVE_STATUS["response"])
    data.update(overrides)
    return data


async def test_energy_live_status_stream_updates(
    hass: HomeAssistant,
    mock_energy_live_stream: MagicMock,
) -> None:
    """A streamed live_status document drives the energy sensor states."""
    await setup_platform(hass, [Platform.SENSOR])

    # The REST cold read populated the fixture values.
    assert hass.states.get("sensor.energy_site_solar_power").state == "1.185"
    assert hass.states.get("sensor.wall_connector_power").state == "0.0"

    live_status = _live_status(solar_power=456)
    live_status["wall_connectors"][0]["wall_connector_power"] = 789
    mock_energy_live_stream.send(live_status)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.energy_site_solar_power").state == "0.456"
    assert hass.states.get("sensor.wall_connector_power").state == "0.789"


@pytest.mark.usefixtures("mock_energy_only")
async def test_energy_only_account_streams_live_status(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_stream_listen: AsyncMock,
    mock_energy_live_stream: MagicMock,
) -> None:
    """An energy-only account starts one stream and streams live_status to sensors."""
    entry = await setup_platform(hass, [Platform.SENSOR])
    assert entry.state is ConfigEntryState.LOADED

    # The account-wide stream is started and the live_status listener registered.
    mock_stream_listen.assert_called_once()
    mock_energy_live_stream.assert_called_once()

    mock_energy_live_stream.send(_live_status(solar_power=999))
    await hass.async_block_till_done()
    assert hass.states.get("sensor.energy_site_solar_power").state == "0.999"

    # Credit sensors are still created for an energy-only account.
    assert entry.unique_id is not None
    assert entity_registry.async_get_entity_id(
        Platform.SENSOR, "teslemetry", f"{entry.unique_id}_credit_quota"
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_vehicle_data: AsyncMock,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that the sensor entities with the legacy polling are correct."""

    freezer.move_to("2024-01-01 00:00:00+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entry = await setup_platform(hass, [Platform.SENSOR])

    assert_entities(hass, entry.entry_id, entity_registry, snapshot)

    # Coordinator refresh
    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert_entities_alt(hass, entry.entry_id, entity_registry, snapshot)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors_streaming(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_vehicle_data: AsyncMock,
    mock_products: AsyncMock,
    mock_add_listener: AsyncMock,
) -> None:
    """Tests that the sensor entities with streaming are correct."""

    freezer.move_to("2024-01-01 00:00:00+00:00")

    # miles_since_reset and self_driving_miles_since_reset are HW4-only fields.
    mock_products.return_value = _products_with_driver_assist("TeslaAP4")

    entry = await setup_platform(hass, [Platform.SENSOR])

    # Stream update
    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "data": {
                Signal.DETAILED_CHARGE_STATE: "DetailedChargeStateCharging",
                Signal.BATTERY_LEVEL: 90,
                Signal.AC_CHARGING_ENERGY_IN: 10,
                Signal.AC_CHARGING_POWER: 2,
                Signal.CHARGING_CABLE_TYPE: None,
                Signal.TIME_TO_FULL_CHARGE: 0.166666667,
                Signal.MINUTES_TO_ARRIVAL: None,
                Signal.LIFETIME_ENERGY_GAINED_REGEN: 1234.5,
                Signal.MILES_SINCE_RESET: 678.9,
                Signal.SELF_DRIVING_MILES_SINCE_RESET: 123.4,
            },
            "credits": {
                "type": "wake_up",
                "cost": 20,
                "name": "wake_up",
                "balance": 1980,
                "quota": {
                    "used": 212,
                    "fraction": 0.212,
                    "reset_at": "2026-07-10T00:00:00.000Z",
                },
            },
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()

    # Balance-only credit events should not clear quota usage.
    mock_add_listener.send(
        {
            "credits": {"balance": 1980},
            "createdAt": "2024-10-04T10:45:18.537Z",
        }
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.teslemetry_command_quota_used").state == "21.2"

    # Reload the entry
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    # Assert the entities restored their values with concrete assertions
    assert hass.states.get("sensor.test_charging").state == "charging"
    assert hass.states.get("sensor.test_battery_level").state == "90"
    assert hass.states.get("sensor.test_charge_energy_added").state == "10"
    assert hass.states.get("sensor.test_charger_power").state == "2"
    assert hass.states.get("sensor.test_charge_cable").state == "unknown"
    assert hass.states.get("sensor.test_time_to_full_charge").state == "unknown"
    assert hass.states.get("sensor.test_time_to_arrival").state == "unknown"
    assert hass.states.get("sensor.teslemetry_command_credits").state == "1980"
    assert (quota_state := hass.states.get("sensor.teslemetry_command_quota_used"))
    assert quota_state.state == "21.2"

    assert (regen := hass.states.get("sensor.test_lifetime_energy_gained_regen"))
    assert regen.state == "1234.5"
    assert regen.attributes["device_class"] == "energy"
    assert regen.attributes["state_class"] == "total_increasing"
    assert regen.attributes["unit_of_measurement"] == "kWh"

    # Distance sensors are declared in native miles, HA displays them in the
    # hass unit system's default (km in tests).
    assert (miles := hass.states.get("sensor.test_miles_since_reset"))
    assert miles.state == "1092.5836416"
    assert miles.attributes["device_class"] == "distance"
    assert miles.attributes["state_class"] == "total_increasing"
    assert miles.attributes["unit_of_measurement"] == "km"

    assert (fsd_miles := hass.states.get("sensor.test_self_driving_miles_since_reset"))
    assert fsd_miles.state == "198.5930496"
    assert fsd_miles.attributes["device_class"] == "distance"
    assert fsd_miles.attributes["state_class"] == "total_increasing"
    assert fsd_miles.attributes["unit_of_measurement"] == "km"

    assert [
        entity_registry.async_get(entity_id)
        for entity_id in (
            "sensor.test_lifetime_energy_gained_regen",
            "sensor.test_miles_since_reset",
            "sensor.test_self_driving_miles_since_reset",
        )
    ] == snapshot


@pytest.mark.parametrize(
    "entity_id",
    [
        pytest.param(
            "sensor.test_lifetime_energy_gained_regen",
            id="lifetime_energy_gained_regen",
        ),
        pytest.param("sensor.test_miles_since_reset", id="miles_since_reset"),
        pytest.param(
            "sensor.test_self_driving_miles_since_reset",
            id="self_driving_miles_since_reset",
        ),
    ],
)
async def test_new_streaming_sensors_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_products: AsyncMock,
    mock_add_listener: AsyncMock,
    entity_id: str,
) -> None:
    """Test the new firmware-2025.44 streaming sensors are disabled-by-default diagnostics."""

    # miles_since_reset and self_driving_miles_since_reset are HW4-only fields.
    mock_products.return_value = _products_with_driver_assist("TeslaAP4")

    await setup_platform(hass, [Platform.SENSOR])

    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert entry.entity_category is EntityCategory.DIAGNOSTIC


@pytest.mark.parametrize(
    "entity_id",
    [
        "sensor.test_miles_since_reset",
        "sensor.test_self_driving_miles_since_reset",
    ],
    ids=["miles_since_reset", "self_driving_miles_since_reset"],
)
@pytest.mark.parametrize(
    ("firmware", "driver_assist", "expected"),
    [
        ("2025.44.25.5", "TeslaAP4", True),
        ("2025.44.25.5", "TeslaAP3", False),
        ("2025.44.25.4", "TeslaAP4", False),
        ("2025.44.25.4", "TeslaAP3", False),
    ],
    ids=[
        "hw4_at_threshold",
        "hw3_at_threshold",
        "hw4_below_threshold",
        "hw3_below_threshold",
    ],
)
async def test_hw4_mileage_sensors_gating(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_metadata: AsyncMock,
    mock_products: AsyncMock,
    mock_add_listener: AsyncMock,
    entity_id: str,
    firmware: str,
    driver_assist: str,
    expected: bool,
) -> None:
    """Test HW4 mileage sensors need both AP4 hardware and qualifying firmware."""

    metadata = deepcopy(METADATA)
    metadata["vehicles"][VEHICLE_VIN]["firmware"] = firmware
    mock_metadata.return_value = metadata

    mock_products.return_value = _products_with_driver_assist(driver_assist)

    await setup_platform(hass, [Platform.SENSOR])

    assert (entity_registry.async_get(entity_id) is not None) is expected


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("signal", "entity_id", "streamed_value", "expected_state"),
    [
        (
            Signal.TPMS_PRESSURE_FL,
            "sensor.test_tire_pressure_front_left",
            2.7,
            # 2.7 atm independently hand-converted to bar (2.7 * 1.01325 = 2.735775)
            PressureConverter.convert(2.735775, UnitOfPressure.BAR, UnitOfPressure.PSI),
        ),
        (
            Signal.TPMS_PRESSURE_FR,
            "sensor.test_tire_pressure_front_right",
            2.7,
            # 2.7 atm independently hand-converted to bar (2.7 * 1.01325 = 2.735775)
            PressureConverter.convert(2.735775, UnitOfPressure.BAR, UnitOfPressure.PSI),
        ),
        (
            Signal.TPMS_PRESSURE_RL,
            "sensor.test_tire_pressure_rear_left",
            2.7,
            # 2.7 atm independently hand-converted to bar (2.7 * 1.01325 = 2.735775)
            PressureConverter.convert(2.735775, UnitOfPressure.BAR, UnitOfPressure.PSI),
        ),
        (
            Signal.TPMS_PRESSURE_RR,
            "sensor.test_tire_pressure_rear_right",
            2.7,
            # 2.7 atm independently hand-converted to bar (2.7 * 1.01325 = 2.735775)
            PressureConverter.convert(2.735775, UnitOfPressure.BAR, UnitOfPressure.PSI),
        ),
        (
            Signal.ISOLATION_RESISTANCE,
            "sensor.test_isolation_resistance",
            2.5,
            2.5,
        ),
    ],
    ids=["tpms_fl", "tpms_fr", "tpms_rl", "tpms_rr", "isolation_resistance"],
)
async def test_sensors_streaming_unit_conversion(
    hass: HomeAssistant,
    mock_vehicle_data: AsyncMock,
    mock_add_listener: AsyncMock,
    signal: Signal,
    entity_id: str,
    streamed_value: float,
    expected_state: float,
) -> None:
    """Test streamed TPMS pressure and isolation resistance are converted to their declared units."""

    await setup_platform(hass, [Platform.SENSOR])

    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "data": {signal: streamed_value},
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == pytest.approx(expected_state)


@pytest.mark.parametrize(
    ("key", "signal", "raw_value", "state"),
    [
        ("di_state_f", Signal.DI_STATE_F, "Standby", "standby"),
        ("di_state_r", Signal.DI_STATE_R, "Standby", "standby"),
        ("di_state_rel", Signal.DI_STATE_REL, "Standby", "standby"),
        ("di_state_rer", Signal.DI_STATE_RER, "Standby", "standby"),
        ("sentry_mode", Signal.SENTRY_MODE, "Armed", "armed"),
        (
            "forward_collision_warning",
            Signal.FORWARD_COLLISION_WARNING,
            "Average",
            "average",
        ),
        (
            "guest_mode_mobile_access_state",
            Signal.GUEST_MODE_MOBILE_ACCESS_STATE,
            "Authenticated",
            "authenticated",
        ),
        (
            "lane_departure_avoidance",
            Signal.LANE_DEPARTURE_AVOIDANCE,
            "Warning",
            "warning",
        ),
        ("powershare_status", Signal.POWERSHARE_STATUS, "Enabled", "enabled"),
        ("powershare_stop_reason", Signal.POWERSHARE_STOP_REASON, "Fault", "fault"),
        ("powershare_type", Signal.POWERSHARE_TYPE, "Home", "home"),
        (
            "scheduled_charging_mode",
            Signal.SCHEDULED_CHARGING_MODE,
            "StartAt",
            "start_at",
        ),
        ("speed_limit_warning", Signal.SPEED_LIMIT_WARNING, "Chime", "chime"),
        ("tonneau_tent_mode", Signal.TONNEAU_TENT_MODE, "Active", "active"),
        ("lights_turn_signal", Signal.LIGHTS_TURN_SIGNAL, "Left", "left"),
        ("hvac_power_state", Signal.HVAC_POWER, "On", "on"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_streaming_enum_none_clears_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_vehicle_data: AsyncMock,
    mock_add_listener: AsyncMock,
    key: str,
    signal: Signal,
    raw_value: str,
    state: str,
) -> None:
    """A None streamed value must clear the entity, not leave it stale."""
    await setup_platform(hass, [Platform.SENSOR])
    vin = VEHICLE_DATA_ALT["response"]["vin"]
    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, f"{vin}-{key}")
    assert entity_id is not None

    mock_add_listener.send(
        {
            "vin": vin,
            "data": {signal: raw_value},
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == state

    mock_add_listener.send(
        {
            "vin": vin,
            "data": {signal: None},
            "createdAt": "2024-10-04T10:45:18.537Z",
        }
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNKNOWN


async def test_energy_history_no_time_series(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_energy_history: AsyncMock,
) -> None:
    """Test energy history coordinator when time_series is not a list."""
    # Mock energy history to return data without time_series as a list

    entry = await setup_platform(hass, [Platform.SENSOR])
    assert entry.state is ConfigEntryState.LOADED

    entity_id = "sensor.energy_site_battery_discharged"
    state = hass.states.get(entity_id)
    assert state.state == STATE_UNKNOWN

    mock_energy_history.return_value = ENERGY_HISTORY_EMPTY

    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_UNAVAILABLE
