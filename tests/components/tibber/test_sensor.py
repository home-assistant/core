"""Tests for the Tibber Data API sensors and coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.recorder import Recorder
from homeassistant.components.tibber.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import create_tibber_device

from tests.common import MockConfigEntry


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
