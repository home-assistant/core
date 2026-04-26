"""Tests for the SolarEdge sensor platform."""

from datetime import timedelta
from unittest.mock import Mock, patch

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
    """Test all sensor entities are created with the correct state and registry entry."""
    with patch("homeassistant.components.solaredge.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_overview_sensors_unavailable_on_api_error(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    solaredge_api: Mock,
) -> None:
    """Test overview-based sensors are unavailable when overview API fails."""
    solaredge_api.get_overview.side_effect = ClientError()

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.solaredge_lifetime_energy")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_storage_level_unknown_when_storage_missing(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    solaredge_api: Mock,
) -> None:
    """Test storage_level returns None (unknown) when site has no storage in flow data."""
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
    solaredge_web_api: Mock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test no sensors are created when only web login auth is configured."""
    await setup_integration(hass, mock_config_entry_web_login)

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry_web_login.entry_id
    )
    assert entries == []


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
    """Test storage sensors are unavailable when the response is missing required keys."""
    solaredge_api.get_storage_data.return_value = bad_response

    await setup_integration(hass, mock_config_entry)

    charge_entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_storage_charge_energy"
    )
    assert charge_entry is not None
    assert hass.states.get(charge_entry).state == STATE_UNAVAILABLE


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

    charge_entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_storage_charge_energy"
    )
    assert charge_entry is None

    # Inventory recovers and reports a battery → storage sensors get created.
    solaredge_api.get_inventory.side_effect = None
    solaredge_api.get_inventory.return_value = valid_inventory

    freezer.tick(INVENTORY_UPDATE_DELAY + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    charge_entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_storage_charge_energy"
    )
    discharge_entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_storage_discharge_energy"
    )
    assert charge_entry is not None
    assert discharge_entry is not None


@pytest.mark.parametrize(
    "storage_response",
    [
        # Empty batteries list inside the storage data
        {"storageData": {"batteries": []}},
        # Battery missing the serialNumber key — skipped by the data service
        {"storageData": {"batteries": [{"telemetries": []}]}},
        # Battery with no telemetries — skipped after the serial check
        {"storageData": {"batteries": [{"serialNumber": "BAT001", "telemetries": []}]}},
        # Battery with a single telemetry — falls into the len < 2 branch
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
) -> None:
    """Test storage data service tolerates batteries without serial / telemetries / single telemetry."""
    solaredge_api.get_storage_data.return_value = storage_response

    await setup_integration(hass, mock_config_entry)

    # Aggregate sensors are still created (inventory has a battery), but their
    # state should be 0.0 (no charge/discharge delta calculated).
    charge_entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_storage_charge_energy"
    )
    assert charge_entry is not None
    state = hass.states.get(charge_entry)
    assert state is not None
    assert state.state in {"0.0", STATE_UNKNOWN}


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_inventory_battery_without_serial_skipped(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    solaredge_api: Mock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test inventory batteries without a serial number are skipped for per-battery sensors."""
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
    """Test storage service stays idle when inventory recovers but reports no batteries."""
    solaredge_api.get_inventory.side_effect = KeyError("Inventory")

    await setup_integration(hass, mock_config_entry)

    # Inventory recovers but reports zero batteries.
    solaredge_api.get_inventory.side_effect = None
    solaredge_api.get_inventory.return_value = {"Inventory": {"batteries": []}}

    freezer.tick(INVENTORY_UPDATE_DELAY + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    charge_entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_storage_charge_energy"
    )
    assert charge_entry is None
