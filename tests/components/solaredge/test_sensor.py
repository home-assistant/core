"""Tests for the SolarEdge sensors."""

from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.recorder import Recorder
from homeassistant.components.solaredge.const import (
    CONF_SITE_ID,
    DEFAULT_NAME,
    DOMAIN,
    INVENTORY_UPDATE_DELAY,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import API_KEY, SITE_ID

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


@pytest.fixture
def mock_solaredge_api() -> AsyncMock:
    """Return a mocked SolarEdge API with common defaults."""
    api = AsyncMock()
    api.get_details = AsyncMock(return_value={"details": {"status": "active"}})
    api.get_overview = AsyncMock(
        return_value={
            "overview": {
                "lifeTimeData": {"energy": 100000},
                "lastYearData": {"energy": 50000},
                "lastMonthData": {"energy": 10000},
                "lastDayData": {"energy": 0.0},
                "currentPower": {"power": 0.0},
            }
        }
    )
    api.get_inventory = AsyncMock(
        return_value={"Inventory": {"batteries": [{"SN": "BAT001"}]}}
    )
    api.get_current_power_flow = AsyncMock(
        return_value={
            "siteCurrentPowerFlow": {
                "unit": "W",
                "connections": [],
            }
        }
    )
    api.get_energy_details = AsyncMock(
        return_value={"energyDetails": {"unit": "Wh", "meters": []}}
    )
    api.get_storage_data = AsyncMock(return_value=STORAGE_DATA_SINGLE_BATTERY)
    return api


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a default mocked config entry for storage tests."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        data={CONF_NAME: DEFAULT_NAME, CONF_SITE_ID: SITE_ID, CONF_API_KEY: API_KEY},
    )


STORAGE_DATA_SINGLE_BATTERY = {
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
            }
        ]
    }
}

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


@patch("homeassistant.components.solaredge.SolarEdge")
async def test_storage_data_service(
    mock_solaredge: MagicMock,
    recorder_mock: Recorder,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_solaredge_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test storage data service fetches battery charge/discharge energy."""
    mock_solaredge.return_value = mock_solaredge_api

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

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

    # Per-battery entities
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


@patch("homeassistant.components.solaredge.SolarEdge")
async def test_storage_data_service_multi_battery(
    mock_solaredge: MagicMock,
    recorder_mock: Recorder,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_solaredge_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test storage data service aggregates data across multiple batteries."""
    mock_solaredge_api.get_inventory = AsyncMock(
        return_value={"Inventory": {"batteries": [{"SN": "BAT001"}, {"SN": "BAT002"}]}}
    )
    mock_solaredge_api.get_storage_data = AsyncMock(
        return_value=STORAGE_DATA_MULTI_BATTERY
    )
    mock_solaredge.return_value = mock_solaredge_api

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

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
    state = hass.states.get(charge_entry)
    assert state is not None
    assert float(state.state) == 1200.0  # 500 + 700

    state = hass.states.get(discharge_entry)
    assert state is not None
    assert float(state.state) == 700.0  # 300 + 400

    # Per-battery entities for BAT001
    bat1_soc = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_BAT001_battery_state_of_charge"
    )
    assert bat1_soc is not None
    state = hass.states.get(bat1_soc)
    assert state is not None
    assert float(state.state) == 75.0

    # Per-battery entities for BAT002
    bat2_charge = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_BAT002_battery_charge_energy"
    )
    bat2_soc = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_BAT002_battery_state_of_charge"
    )
    assert bat2_charge is not None
    assert bat2_soc is not None

    state = hass.states.get(bat2_charge)
    assert state is not None
    assert float(state.state) == 700.0

    state = hass.states.get(bat2_soc)
    assert state is not None
    assert float(state.state) == 80.0


@patch("homeassistant.components.solaredge.SolarEdge")
async def test_storage_data_service_no_batteries(
    mock_solaredge: MagicMock,
    recorder_mock: Recorder,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_solaredge_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test storage service is not created when no batteries in inventory."""
    mock_solaredge_api.get_inventory = AsyncMock(
        return_value={"Inventory": {"batteries": []}}
    )
    mock_solaredge.return_value = mock_solaredge_api

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Sensors should not exist when inventory reports no batteries
    charge_entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_storage_charge_energy"
    )
    discharge_entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_storage_discharge_energy"
    )
    assert charge_entry is None
    assert discharge_entry is None


@patch("homeassistant.components.solaredge.SolarEdge")
async def test_storage_data_service_api_error(
    mock_solaredge: MagicMock,
    recorder_mock: Recorder,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_solaredge_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test storage data service handles API errors gracefully."""
    mock_solaredge_api.get_storage_data = AsyncMock(side_effect=Exception("API error"))
    mock_solaredge.return_value = mock_solaredge_api

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    charge_entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_storage_charge_energy"
    )
    discharge_entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_storage_discharge_energy"
    )
    assert charge_entry is not None
    assert discharge_entry is not None

    # Sensors should be unavailable when the API returns an error
    state = hass.states.get(charge_entry)
    assert state is not None
    assert state.state == "unavailable"

    state = hass.states.get(discharge_entry)
    assert state is not None
    assert state.state == "unavailable"


@patch("homeassistant.components.solaredge.SolarEdge")
async def test_storage_data_missing_keys_in_response(
    mock_solaredge: MagicMock,
    recorder_mock: Recorder,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_solaredge_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test storage service raises UpdateFailed when response is missing required keys."""
    # API returns a response but without the storageData key
    mock_solaredge_api.get_storage_data = AsyncMock(return_value={"unexpected": {}})
    mock_solaredge.return_value = mock_solaredge_api

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    charge_entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_storage_charge_energy"
    )
    discharge_entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_storage_discharge_energy"
    )
    assert charge_entry is not None
    assert discharge_entry is not None

    # Sensors should be unavailable due to UpdateFailed from missing key
    state = hass.states.get(charge_entry)
    assert state is not None
    assert state.state == "unavailable"

    state = hass.states.get(discharge_entry)
    assert state is not None
    assert state.state == "unavailable"


@patch("homeassistant.components.solaredge.SolarEdge")
async def test_storage_data_missing_batteries_key(
    mock_solaredge: MagicMock,
    recorder_mock: Recorder,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_solaredge_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test storage service raises UpdateFailed when batteries key is missing."""
    # API returns storageData but without batteries key
    mock_solaredge_api.get_storage_data = AsyncMock(
        return_value={"storageData": {"otherField": "value"}}
    )
    mock_solaredge.return_value = mock_solaredge_api

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    charge_entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_storage_charge_energy"
    )
    assert charge_entry is not None

    state = hass.states.get(charge_entry)
    assert state is not None
    assert state.state == "unavailable"


@patch("homeassistant.components.solaredge.SolarEdge")
async def test_storage_service_deferred_after_inventory_failure(
    mock_solaredge: MagicMock,
    recorder_mock: Recorder,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_solaredge_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test storage service is created after inventory recovers from failure."""
    # Initial inventory fetch fails
    mock_solaredge_api.get_inventory = AsyncMock(side_effect=KeyError("Inventory"))
    mock_solaredge.return_value = mock_solaredge_api

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Storage sensors should not exist yet
    charge_entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_storage_charge_energy"
    )
    assert charge_entry is None

    # Now inventory recovers and reports batteries
    mock_solaredge_api.get_inventory = AsyncMock(
        return_value={"Inventory": {"batteries": [{"SN": "BAT001"}]}}
    )
    mock_solaredge_api.get_storage_data = AsyncMock(
        return_value=STORAGE_DATA_SINGLE_BATTERY
    )

    # Trigger inventory coordinator refresh
    freezer.tick(INVENTORY_UPDATE_DELAY)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Storage sensors should now exist
    charge_entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_storage_charge_energy"
    )
    discharge_entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SITE_ID}_storage_discharge_energy"
    )
    assert charge_entry is not None
    assert discharge_entry is not None


@patch("homeassistant.components.solaredge.SolarEdge")
async def test_storage_service_not_created_when_inventory_has_no_batteries(
    mock_solaredge: MagicMock,
    recorder_mock: Recorder,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_solaredge_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test storage service is not retried when inventory succeeds with no batteries."""
    # Initial inventory fails
    mock_solaredge_api.get_inventory = AsyncMock(side_effect=KeyError("Inventory"))
    mock_solaredge.return_value = mock_solaredge_api

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Inventory recovers but reports zero batteries
    mock_solaredge_api.get_inventory = AsyncMock(
        return_value={"Inventory": {"batteries": []}}
    )

    freezer.tick(INVENTORY_UPDATE_DELAY)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Storage sensors should still not exist
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
@patch("homeassistant.components.solaredge.SolarEdge")
async def test_power_flow_direction_sensors(
    mock_solaredge: MagicMock,
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_solaredge_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    grid_export: bool,
    storage_charging: bool,
    expected_grid: str,
    expected_storage: str,
) -> None:
    """Test that grid and storage flow direction ENUM sensors are populated."""
    mock_solaredge_api.get_current_power_flow = AsyncMock(
        return_value=_power_flow_payload(
            grid_export=grid_export, storage_charging=storage_charging
        )
    )
    mock_solaredge.return_value = mock_solaredge_api

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


@patch("homeassistant.components.solaredge.SolarEdge")
async def test_storage_level_from_power_flow(
    mock_solaredge: MagicMock,
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_solaredge_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the storage level sensor reads chargeLevel from power-flow data."""
    mock_solaredge_api.get_current_power_flow = AsyncMock(
        return_value=_power_flow_payload(
            grid_export=False, storage_charging=True, charge_level=42
        )
    )
    mock_solaredge.return_value = mock_solaredge_api

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.solaredge_storage_level")
    assert state is not None
    assert state.state == "42"


@patch("homeassistant.components.solaredge.SolarEdge")
async def test_power_flow_direction_sensors_missing_connections(
    mock_solaredge: MagicMock,
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_solaredge_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test direction sensors stay unknown when power flow has no connections."""
    mock_solaredge.return_value = mock_solaredge_api

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
