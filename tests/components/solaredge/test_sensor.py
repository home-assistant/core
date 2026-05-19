"""Tests for the SolarEdge sensor platform."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.recorder import Recorder
from homeassistant.components.solaredge.const import DOMAIN, INVENTORY_UPDATE_DELAY
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import SITE_ID

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

STORAGE_DATA_MULTI_BATTERY = {
    "storageData": {
        "batteries": [
            {
                "serialNumber": "BAT001",
                "telemetries": [
                    {
                        "timeStamp": "2025-01-01 00:00:00",
                        "lifeTimeEnergyCharged": 1000.0,
                        "lifeTimeEnergyDischarged": 500.0,
                        "batteryPercentageState": 50.0,
                        "power": 100.0,
                    },
                    {
                        "timeStamp": "2025-01-01 12:00:00",
                        "lifeTimeEnergyCharged": 1500.0,
                        "lifeTimeEnergyDischarged": 800.0,
                        "batteryPercentageState": 75.0,
                        "power": 200.0,
                    },
                ],
            },
            {
                "serialNumber": "BAT002",
                "telemetries": [
                    {
                        "timeStamp": "2025-01-01 00:00:00",
                        "lifeTimeEnergyCharged": 2000.0,
                        "lifeTimeEnergyDischarged": 1000.0,
                        "batteryPercentageState": 40.0,
                        "power": 150.0,
                    },
                    {
                        "timeStamp": "2025-01-01 12:00:00",
                        "lifeTimeEnergyCharged": 2700.0,
                        "lifeTimeEnergyDischarged": 1400.0,
                        "batteryPercentageState": 80.0,
                        "power": 250.0,
                    },
                ],
            },
        ]
    }
}


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    solaredge_api: Mock,
) -> None:
    """Test all sensors are created with correct state and registry."""
    with patch("homeassistant.components.solaredge.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_overview_sensors_unavailable_on_api_error(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    solaredge_api: Mock,
) -> None:
    """Test overview-based sensors are unavailable when overview API fails."""
    solaredge_api.get_overview.side_effect = ClientError()

    await setup_integration(hass, mock_config_entry)

    for sensor_id in (
        "sensor.solaredge_lifetime_energy",
        "sensor.solaredge_energy_this_year",
        "sensor.solaredge_energy_this_month",
        "sensor.solaredge_energy_today",
        "sensor.solaredge_current_power",
    ):
        state = hass.states.get(sensor_id)
        assert state is not None, sensor_id
        assert state.state == STATE_UNAVAILABLE, sensor_id


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_storage_level_unknown_when_storage_missing(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    solaredge_api: Mock,
) -> None:
    """Test storage_level returns None when site has no storage."""
    power_flow = solaredge_api.get_current_power_flow.return_value
    power_flow["siteCurrentPowerFlow"].pop("STORAGE")
    # Drop STORAGE from connections too so the data service does not reference it.
    power_flow["siteCurrentPowerFlow"]["connections"] = [
        {"from": "GRID", "to": "Load"},
        {"from": "PV", "to": "Load"},
    ]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.solaredge_storage_level")
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_no_sensors_without_api_key(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry_web_login: MockConfigEntry,
    solaredge_web_api: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test no sensors are created when only web login auth is configured."""
    await setup_integration(hass, mock_config_entry_web_login)

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry_web_login.entry_id
    )
    assert entries == []


@pytest.mark.parametrize(
    ("api_method", "sensor_id"),
    [
        ("get_overview", "sensor.solaredge_lifetime_energy"),
        ("get_inventory", "sensor.solaredge_inverters"),
        ("get_current_power_flow", "sensor.solaredge_grid_power"),
        ("get_energy_details", "sensor.solaredge_produced_energy"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_unavailable_on_data_service_keyerror(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    solaredge_api: Mock,
    api_method: str,
    sensor_id: str,
) -> None:
    """Test sensors become unavailable on UpdateFailed."""
    getattr(solaredge_api, api_method).return_value = {}

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(sensor_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_details_sensor_unavailable_on_data_service_keyerror(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    solaredge_api: Mock,
) -> None:
    """Test the details sensor becomes unavailable when its refresh fails.

    `get_details` is also called during setup validation, so the first call
    must succeed; subsequent calls (the data service refresh) return data
    without the 'details' key to trigger UpdateFailed.
    """
    solaredge_api.get_details.side_effect = [
        {"details": {"status": "Active"}},
        {},
    ]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.solaredge_site_details")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_energy_details_sensor_unknown_when_no_meters(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    solaredge_api: Mock,
) -> None:
    """Test energy detail sensors stay unknown when the API reports no meters."""
    solaredge_api.get_energy_details.return_value = {"energyDetails": {"unit": "Wh"}}

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.solaredge_produced_energy")
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_energy_details_filters_meters(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    solaredge_api: Mock,
) -> None:
    """Test energy details skips meters without type/values."""
    solaredge_api.get_energy_details.return_value = {
        "energyDetails": {
            "unit": "Wh",
            "meters": [
                {"type": "Production"},  # missing values, skipped
                {"values": [{"date": "2025-01-01", "value": 1.0}]},  # missing type
                {
                    "type": "SomethingElse",  # unsupported type, skipped
                    "values": [{"date": "2025-01-01", "value": 2.0}],
                },
                {
                    "type": "Production",
                    "values": [{"date": "2025-01-01", "value": 100.0}],
                },
            ],
        }
    }

    await setup_integration(hass, mock_config_entry)

    produced = hass.states.get("sensor.solaredge_produced_energy")
    assert produced is not None
    assert produced.state == "100.0"
    assert produced.attributes["date"] == "2025-01-01"

    consumed = hass.states.get("sensor.solaredge_consumed_energy")
    assert consumed is not None
    assert consumed.state == STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_power_flow_sensor_unknown_when_no_connections(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    solaredge_api: Mock,
) -> None:
    """Test power flow sensors stay unknown when the API reports no connections."""
    solaredge_api.get_current_power_flow.return_value = {
        "siteCurrentPowerFlow": {"unit": "W"}
    }

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.solaredge_grid_power")
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_power_flow_grid_export_storage_discharge(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    solaredge_api: Mock,
) -> None:
    """Test power flow sign flipping for grid export and storage."""
    solaredge_api.get_current_power_flow.return_value = {
        "siteCurrentPowerFlow": {
            "unit": "W",
            "connections": [
                {"from": "PV", "to": "GRID"},
                {"from": "STORAGE", "to": "Load"},
            ],
            "GRID": {"status": "Active", "currentPower": 100.0},
            "LOAD": {"status": "Active", "currentPower": 500.0},
            "PV": {"status": "Active", "currentPower": 600.0},
            "STORAGE": {
                "status": "Discharging",
                "currentPower": 400.0,
                "chargeLevel": 60,
            },
        }
    }

    await setup_integration(hass, mock_config_entry)

    grid = hass.states.get("sensor.solaredge_grid_power")
    assert grid is not None
    assert grid.state == "-100.0"

    storage = hass.states.get("sensor.solaredge_storage_power")
    assert storage is not None
    assert storage.state == "400.0"

    grid_direction = hass.states.get("sensor.solaredge_grid_flow_direction")
    assert grid_direction is not None
    assert grid_direction.state == "export"

    storage_direction = hass.states.get("sensor.solaredge_storage_flow_direction")
    assert storage_direction is not None
    assert storage_direction.state == "discharge"

    storage_level = hass.states.get("sensor.solaredge_storage_level")
    assert storage_level is not None
    assert storage_level.state == "60"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_power_flow_zero_current_power_keeps_zero(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    solaredge_api: Mock,
) -> None:
    """Test power flow leaves zero values untouched (no -0 in the state)."""
    solaredge_api.get_current_power_flow.return_value = {
        "siteCurrentPowerFlow": {
            "unit": "W",
            "connections": [{"from": "PV", "to": "GRID"}],
            "GRID": {"status": "Idle", "currentPower": 0},
            "STORAGE": {"status": "Idle", "currentPower": 0, "chargeLevel": 50},
        }
    }

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.solaredge_grid_power").state == "0"
    assert hass.states.get("sensor.solaredge_storage_power").state == "0"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_storage_data_service(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    solaredge_api: Mock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test storage data service fetches battery charge/discharge energy."""
    await setup_integration(hass, mock_config_entry)

    # Aggregate sensors
    charge_entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_storage_charge_energy"
    )
    discharge_entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_storage_discharge_energy"
    )
    assert charge_entry is not None
    assert discharge_entry is not None

    state = hass.states.get(charge_entry)
    assert state is not None
    assert float(state.state) == 500.0  # 1500 - 1000

    state = hass.states.get(discharge_entry)
    assert state is not None
    assert float(state.state) == 300.0  # 800 - 500

    # Per-battery entities for BAT001
    bat_charge = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_BAT001_battery_charge_energy"
    )
    bat_discharge = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_BAT001_battery_discharge_energy"
    )
    bat_soc = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_BAT001_battery_state_of_charge"
    )
    bat_power = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_BAT001_battery_power"
    )
    assert bat_charge is not None
    assert bat_discharge is not None
    assert bat_soc is not None
    assert bat_power is not None

    state = hass.states.get(bat_charge)
    assert state is not None
    assert float(state.state) == 500.0

    state = hass.states.get(bat_discharge)
    assert state is not None
    assert float(state.state) == 300.0

    state = hass.states.get(bat_soc)
    assert state is not None
    assert float(state.state) == 75.0

    state = hass.states.get(bat_power)
    assert state is not None
    assert float(state.state) == 200.0


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_storage_data_service_multi_battery(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    solaredge_api: Mock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test storage data service aggregates data across multiple batteries."""
    inventory = solaredge_api.get_inventory.return_value
    inventory["Inventory"]["batteries"] = [{"SN": "BAT001"}, {"SN": "BAT002"}]
    solaredge_api.get_storage_data.return_value = STORAGE_DATA_MULTI_BATTERY

    await setup_integration(hass, mock_config_entry)

    charge_entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_storage_charge_energy"
    )
    discharge_entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_storage_discharge_energy"
    )
    assert charge_entry is not None
    assert discharge_entry is not None

    # BAT001: charge=500 (1500-1000), discharge=300 (800-500)
    # BAT002: charge=700 (2700-2000), discharge=400 (1400-1000)
    assert float(hass.states.get(charge_entry).state) == 1200.0
    assert float(hass.states.get(discharge_entry).state) == 700.0

    bat1_soc = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_BAT001_battery_state_of_charge"
    )
    assert bat1_soc is not None
    assert float(hass.states.get(bat1_soc).state) == 75.0

    bat2_charge = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_BAT002_battery_charge_energy"
    )
    bat2_soc = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_BAT002_battery_state_of_charge"
    )
    assert bat2_charge is not None
    assert bat2_soc is not None
    assert float(hass.states.get(bat2_charge).state) == 700.0
    assert float(hass.states.get(bat2_soc).state) == 80.0


async def test_storage_service_not_created_when_inventory_has_no_batteries(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    solaredge_api: Mock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test storage service is not created when no batteries in inventory."""
    inventory = solaredge_api.get_inventory.return_value
    inventory["Inventory"]["batteries"] = []

    await setup_integration(hass, mock_config_entry)

    charge_entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_storage_charge_energy"
    )
    discharge_entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_storage_discharge_energy"
    )
    assert charge_entry is None
    assert discharge_entry is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_storage_data_service_api_error(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    solaredge_api: Mock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test storage sensors are unavailable when the storage API errors out."""
    solaredge_api.get_storage_data.side_effect = Exception("API error")

    await setup_integration(hass, mock_config_entry)

    charge_entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_storage_charge_energy"
    )
    discharge_entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_storage_discharge_energy"
    )
    assert charge_entry is not None
    assert discharge_entry is not None

    assert hass.states.get(charge_entry).state == STATE_UNAVAILABLE
    assert hass.states.get(discharge_entry).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "bad_response",
    [{"unexpected": {}}, {"storageData": {"otherField": "value"}}],
    ids=["missing_storageData", "missing_batteries"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_storage_data_missing_keys_in_response(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    solaredge_api: Mock,
    entity_registry: er.EntityRegistry,
    bad_response: dict,
) -> None:
    """Test storage sensors unavailable with missing required keys."""
    solaredge_api.get_storage_data.return_value = bad_response

    await setup_integration(hass, mock_config_entry)

    charge_entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_storage_charge_energy"
    )
    discharge_entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_storage_discharge_energy"
    )
    assert charge_entry is not None
    assert discharge_entry is not None
    assert hass.states.get(charge_entry).state == STATE_UNAVAILABLE
    assert hass.states.get(discharge_entry).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_storage_service_deferred_after_inventory_failure(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    solaredge_api: Mock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test storage service is created after inventory recovers from a failure."""
    valid_inventory = solaredge_api.get_inventory.return_value
    solaredge_api.get_inventory.side_effect = KeyError("Inventory")

    await setup_integration(hass, mock_config_entry)

    # Storage sensors are not created yet — the inventory fetch failed.
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{SITE_ID}_storage_charge_energy"
        )
        is None
    )

    # Inventory recovers and reports a battery → storage sensors get created.
    solaredge_api.get_inventory.side_effect = None
    solaredge_api.get_inventory.return_value = valid_inventory

    freezer.tick(INVENTORY_UPDATE_DELAY)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{SITE_ID}_storage_charge_energy"
        )
        is not None
    )
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{SITE_ID}_storage_discharge_energy"
        )
        is not None
    )


@pytest.mark.parametrize(
    ("storage_response", "expected_charge_state"),
    [
        # Empty batteries list → data service returns early, aggregate stays unset.
        ({"storageData": {"batteries": []}}, STATE_UNKNOWN),
        # Battery missing the serialNumber key → skipped in the loop, aggregate
        # falls through with the initial 0.0 totals.
        ({"storageData": {"batteries": [{"telemetries": []}]}}, "0.0"),
        # Battery with no telemetries → skipped after the serial check.
        (
            {
                "storageData": {
                    "batteries": [{"serialNumber": "BAT001", "telemetries": []}]
                }
            },
            "0.0",
        ),
        # Battery with a single telemetry → can't compute a delta, contributes
        # 0.0 to the aggregate via the len < 2 branch.
        (
            {
                "storageData": {
                    "batteries": [
                        {
                            "serialNumber": "BAT001",
                            "telemetries": [
                                {
                                    "timeStamp": "2025-01-01 00:00:00",
                                    "lifeTimeEnergyCharged": 1000.0,
                                    "lifeTimeEnergyDischarged": 500.0,
                                    "batteryPercentageState": 50.0,
                                    "power": 100.0,
                                }
                            ],
                        }
                    ]
                }
            },
            "0.0",
        ),
    ],
    ids=[
        "empty_batteries",
        "battery_without_serial",
        "battery_without_telemetries",
        "battery_with_single_telemetry",
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_storage_data_service_handles_malformed_responses(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    solaredge_api: Mock,
    entity_registry: er.EntityRegistry,
    storage_response: dict,
    expected_charge_state: str,
) -> None:
    """Test storage tolerates batteries without serial/telemetries."""
    solaredge_api.get_storage_data.return_value = storage_response

    await setup_integration(hass, mock_config_entry)

    charge_entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_storage_charge_energy"
    )
    assert charge_entry is not None
    state = hass.states.get(charge_entry)
    assert state is not None
    assert state.state == expected_charge_state


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_inventory_battery_without_serial_skipped(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    solaredge_api: Mock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test batteries without serial are skipped for per-battery sensors."""
    inventory = solaredge_api.get_inventory.return_value
    inventory["Inventory"]["batteries"] = [{"name": "Battery without serial"}]

    await setup_integration(hass, mock_config_entry)

    # Aggregate sensors are still created (battery exists in inventory)
    charge_entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_storage_charge_energy"
    )
    assert charge_entry is not None

    # No per-battery sensors because the battery has no serial.
    # Per-battery unique_ids follow `{site_id}_{serial}_battery_{key}`.
    per_battery_entries = [
        e
        for e in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if "_battery_" in e.unique_id
    ]
    assert per_battery_entries == []


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_storage_service_not_retried_after_recovery_with_no_batteries(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    solaredge_api: Mock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test storage stays idle when inventory has no batteries."""
    solaredge_api.get_inventory.side_effect = KeyError("Inventory")

    await setup_integration(hass, mock_config_entry)

    # Inventory recovers but reports zero batteries.
    solaredge_api.get_inventory.side_effect = None
    solaredge_api.get_inventory.return_value = {"Inventory": {"batteries": []}}

    freezer.tick(INVENTORY_UPDATE_DELAY)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    charge_entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_storage_charge_energy"
    )
    assert charge_entry is None


def _power_flow_payload(
    *,
    grid_export: bool,
    storage_charging: bool,
    charge_level: int = 60,
) -> dict[str, dict]:
    """Build a siteCurrentPowerFlow payload for the given grid/storage flows."""
    if grid_export:
        grid_connection = {"from": "LOAD", "to": "Grid"}
    else:
        grid_connection = {"from": "GRID", "to": "Load"}
    if storage_charging:
        storage_connection = {"from": "PV", "to": "Storage"}
    else:
        storage_connection = {"from": "STORAGE", "to": "Load"}
    return {
        "siteCurrentPowerFlow": {
            "unit": "W",
            "connections": [grid_connection, storage_connection],
            "GRID": {"status": "Active", "currentPower": 1200.0},
            "LOAD": {"status": "Active", "currentPower": 800.0},
            "PV": {"status": "Active", "currentPower": 2000.0},
            "STORAGE": {
                "status": "Charging" if storage_charging else "Discharging",
                "currentPower": 300.0,
                "chargeLevel": charge_level,
            },
        }
    }


@pytest.mark.parametrize(
    ("grid_export", "storage_charging", "expected_grid", "expected_storage"),
    [
        (True, False, "export", "discharge"),
        (False, True, "import", "charge"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@patch("homeassistant.components.solaredge.SolarEdge")
async def test_power_flow_direction_sensors(
    mock_solaredge: MagicMock,
    recorder_mock: Recorder,
    hass: HomeAssistant,
    solaredge_api: Mock,
    mock_config_entry: MockConfigEntry,
    grid_export: bool,
    storage_charging: bool,
    expected_grid: str,
    expected_storage: str,
) -> None:
    """Test that grid and storage flow direction ENUM sensors are populated."""
    solaredge_api.get_current_power_flow = AsyncMock(
        return_value=_power_flow_payload(
            grid_export=grid_export, storage_charging=storage_charging
        )
    )
    mock_solaredge.return_value = solaredge_api

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    grid_dir = hass.states.get("sensor.solaredge_grid_flow_direction")
    assert grid_dir is not None
    assert grid_dir.state == expected_grid
    assert grid_dir.attributes["options"] == ["export", "import"]
    assert grid_dir.attributes["device_class"] == "enum"

    storage_dir = hass.states.get("sensor.solaredge_storage_flow_direction")
    assert storage_dir is not None
    assert storage_dir.state == expected_storage
    assert storage_dir.attributes["options"] == ["charge", "discharge"]
    assert storage_dir.attributes["device_class"] == "enum"

    # Power sensors must no longer expose flow/soc attributes
    grid_power = hass.states.get("sensor.solaredge_grid_power")
    assert grid_power is not None
    assert "flow" not in grid_power.attributes

    storage_power = hass.states.get("sensor.solaredge_storage_power")
    assert storage_power is not None
    assert "flow" not in storage_power.attributes
    assert "soc" not in storage_power.attributes


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@patch("homeassistant.components.solaredge.SolarEdge")
async def test_storage_level_from_power_flow(
    mock_solaredge: MagicMock,
    recorder_mock: Recorder,
    hass: HomeAssistant,
    solaredge_api: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the storage level sensor reads chargeLevel from power-flow data."""
    solaredge_api.get_current_power_flow = AsyncMock(
        return_value=_power_flow_payload(
            grid_export=False, storage_charging=True, charge_level=42
        )
    )
    mock_solaredge.return_value = solaredge_api

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.solaredge_storage_level")
    assert state is not None
    assert state.state == "42"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@patch("homeassistant.components.solaredge.SolarEdge")
async def test_power_flow_direction_sensors_missing_connections(
    mock_solaredge: MagicMock,
    recorder_mock: Recorder,
    hass: HomeAssistant,
    solaredge_api: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test direction sensors stay unknown when power flow has no connections."""
    solaredge_api.get_current_power_flow = AsyncMock(
        return_value={"siteCurrentPowerFlow": {"unit": "W"}}
    )
    mock_solaredge.return_value = solaredge_api

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    grid_dir = hass.states.get("sensor.solaredge_grid_flow_direction")
    assert grid_dir is not None
    assert grid_dir.state == "unknown"

    storage_dir = hass.states.get("sensor.solaredge_storage_flow_direction")
    assert storage_dir is not None
    assert storage_dir.state == "unknown"

    storage_level = hass.states.get("sensor.solaredge_storage_level")
    assert storage_level is not None
    assert storage_level.state == "unknown"
