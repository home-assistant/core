"""Tests for the Tibber Data API sensors and coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.recorder import Recorder
from homeassistant.components.tibber.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.util import dt as dt_util

from .conftest import create_tibber_device

from tests.common import MockConfigEntry


def _create_home(*, current_price: float | None = 1.25) -> MagicMock:
    """Create a mocked Tibber home with an active subscription."""
    home = MagicMock()
    home.home_id = "home-id"
    home.name = "Home"
    home.currency = "NOK"
    home.price_unit = "NOK/kWh"
    home.has_active_subscription = True
    home.has_real_time_consumption = False
    home.last_data_timestamp = None
    home.update_info = AsyncMock(return_value=None)
    home.update_info_and_price_info = AsyncMock(return_value=None)
    home.current_price_data = MagicMock(
        return_value=(current_price, dt_util.utcnow(), 0.4)
    )
    home.current_attributes = MagicMock(
        return_value={
            "max_price": 1.8,
            "avg_price": 1.2,
            "min_price": 0.8,
            "off_peak_1": 0.9,
            "peak": 1.7,
            "off_peak_2": 1.0,
        }
    )
    home.month_cost = 111.1
    home.peak_hour = 2.5
    home.peak_hour_time = dt_util.utcnow()
    home.month_cons = 222.2
    home.hourly_consumption_data = []
    home.hourly_production_data = []
    home.info = {
        "viewer": {
            "home": {
                "appNickname": "Home",
                "address": {"address1": "Street 1"},
                "meteringPointData": {
                    "gridCompany": "GridCo",
                    "estimatedAnnualConsumption": 12000,
                },
            }
        }
    }
    return home


async def test_price_sensor_state_unit_and_attributes(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    tibber_mock: MagicMock,
    setup_credentials: None,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test price sensor state and attributes."""
    home = _create_home(current_price=1.25)
    tibber_mock.get_homes.return_value = [home]

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, home.home_id)
    assert entity_id is not None

    await async_update_entity(hass, entity_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == 1.25
    assert state.attributes["unit_of_measurement"] == "NOK/kWh"
    assert state.attributes["app_nickname"] == "Home"
    assert state.attributes["grid_company"] == "GridCo"
    assert state.attributes["estimated_annual_consumption"] == 12000
    assert state.attributes["intraday_price_ranking"] == 0.4
    assert state.attributes["max_price"] == 1.8
    assert state.attributes["avg_price"] == 1.2
    assert state.attributes["min_price"] == 0.8
    assert state.attributes["off_peak_1"] == 0.9
    assert state.attributes["peak"] == 1.7
    assert state.attributes["off_peak_2"] == 1.0


async def test_data_api_sensors_are_created(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    data_api_client_mock: AsyncMock,
    setup_credentials: None,
    entity_registry: er.EntityRegistry,
) -> None:
    """Ensure Data API sensors are created and expose values from the coordinator."""
    data_api_client_mock.get_all_devices = AsyncMock(
        return_value={"device-id": create_tibber_device(state_of_charge=72.0)}
    )
    data_api_client_mock.update_devices = AsyncMock(
        return_value={"device-id": create_tibber_device(state_of_charge=83.0)}
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    data_api_client_mock.get_all_devices.assert_awaited_once()
    data_api_client_mock.update_devices.assert_awaited_once()

    unique_id = "external-id_storage.stateOfCharge"
    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == 83.0


@pytest.mark.parametrize(
    ("sensor_id", "expected_value", "description"),
    [
        ("storage.ratedCapacity", 10000.0, "Storage rated capacity"),
        ("storage.ratedPower", 5000.0, "Storage rated power"),
        ("storage.availableEnergy", 7500.0, "Storage available energy"),
        ("powerFlow.battery.power", 2500.0, "Battery power flow"),
        ("powerFlow.grid.power", 1500.0, "Grid power flow"),
        ("powerFlow.load.power", 4000.0, "Load power flow"),
        ("powerFlow.toGrid", 25.5, "Power flow to grid percentage"),
        ("powerFlow.toLoad", 60.0, "Power flow to load percentage"),
        ("powerFlow.fromGrid", 15.0, "Power flow from grid percentage"),
        ("powerFlow.fromLoad", 10.0, "Power flow from load percentage"),
        ("energyFlow.hour.battery.charged", 2000.0, "Hourly battery charged"),
        ("energyFlow.hour.battery.discharged", 1500.0, "Hourly battery discharged"),
        ("energyFlow.hour.grid.imported", 1000.0, "Hourly grid imported"),
        ("energyFlow.hour.grid.exported", 800.0, "Hourly grid exported"),
        ("energyFlow.hour.load.consumed", 3000.0, "Hourly load consumed"),
        ("energyFlow.hour.load.generated", 200.0, "Hourly load generated"),
        ("energyFlow.month.battery.charged", 50000.0, "Monthly battery charged"),
        ("energyFlow.month.battery.discharged", 40000.0, "Monthly battery discharged"),
        ("energyFlow.month.grid.imported", 25000.0, "Monthly grid imported"),
        ("energyFlow.month.grid.exported", 20000.0, "Monthly grid exported"),
        ("energyFlow.month.load.consumed", 60000.0, "Monthly load consumed"),
        ("energyFlow.month.load.generated", 5000.0, "Monthly load generated"),
        ("range.remaining", 250.5, "Remaining range"),
        ("charging.current.max", 32.0, "Max charging current"),
        ("charging.current.offlineFallback", 16.0, "Offline fallback charging current"),
        ("temp.setpoint", 22.5, "Temperature setpoint"),
        ("temp.current", 21.0, "Current temperature"),
        ("temp.comfort", 20.5, "Comfort temperature"),
        ("grid.phaseCount", 3.0, "Grid phase count"),
    ],
)
async def test_new_data_api_sensor_values(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    data_api_client_mock: AsyncMock,
    setup_credentials: None,
    entity_registry: er.EntityRegistry,
    sensor_id: str,
    expected_value: float,
    description: str,
) -> None:
    """Test individual new Data API sensor values."""
    device = create_tibber_device(sensor_values={sensor_id: expected_value})
    data_api_client_mock.get_all_devices = AsyncMock(return_value={"device-id": device})
    data_api_client_mock.update_devices = AsyncMock(return_value={"device-id": device})

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    unique_id = f"external-id_{sensor_id}"
    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id is not None, f"Entity not found for {description}"

    state = hass.states.get(entity_id)
    assert state is not None, f"State not found for {description}"
    assert float(state.state) == expected_value, (
        f"Expected {expected_value} for {description}, got {state.state}"
    )


async def test_new_data_api_sensors_with_disabled_by_default(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    data_api_client_mock: AsyncMock,
    setup_credentials: None,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that sensors with entity_registry_enabled_default=False are disabled by default."""
    sensor_values = {
        "cellular.rssi": -75.0,
        "energyFlow.hour.battery.source.grid": 500.0,
        "energyFlow.hour.battery.source.load": 300.0,
        "energyFlow.hour.load.source.battery": 700.0,
        "energyFlow.hour.load.source.grid": 500.0,
        "energyFlow.month.battery.source.grid": 10000.0,
        "energyFlow.month.battery.source.battery": 5000.0,
        "energyFlow.month.battery.source.load": 8000.0,
        "energyFlow.month.grid.source.battery": 3000.0,
        "energyFlow.month.grid.source.grid": 1000.0,
        "energyFlow.month.grid.source.load": 2000.0,
        "energyFlow.month.load.source.battery": 15000.0,
        "energyFlow.month.load.source.grid": 10000.0,
    }

    device = create_tibber_device(sensor_values=sensor_values)
    data_api_client_mock.get_all_devices = AsyncMock(return_value={"device-id": device})
    data_api_client_mock.update_devices = AsyncMock(return_value={"device-id": device})

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    disabled_sensors = [
        "cellular.rssi",
        "energyFlow.hour.battery.source.grid",
        "energyFlow.hour.battery.source.load",
        "energyFlow.hour.load.source.battery",
        "energyFlow.hour.load.source.grid",
        "energyFlow.month.battery.source.grid",
        "energyFlow.month.battery.source.battery",
        "energyFlow.month.battery.source.load",
        "energyFlow.month.grid.source.battery",
        "energyFlow.month.grid.source.grid",
        "energyFlow.month.grid.source.load",
        "energyFlow.month.load.source.battery",
        "energyFlow.month.load.source.grid",
    ]

    for sensor_id in disabled_sensors:
        unique_id = f"external-id_{sensor_id}"
        entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        assert entity_id is not None, f"Entity not found for sensor {sensor_id}"

        entity_entry = entity_registry.async_get(entity_id)
        assert entity_entry is not None
        assert entity_entry.disabled, (
            f"Sensor {sensor_id} should be disabled by default"
        )
