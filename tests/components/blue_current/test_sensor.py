"""The tests for Blue current sensors."""

from datetime import datetime

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry

charge_point = {
    "evse_id": "101",
    "model_type": "",
    "name": "",
}


charge_point_status = {
    "actual_v1": 14,
    "actual_v2": 18,
    "actual_v3": 15,
    "actual_p1": 19,
    "actual_p2": 14,
    "actual_p3": 15,
    "activity": "available",
    "total_cost": 13.32,
    "avg_current": 16,
    "avg_voltage": 15.7,
    "total_kw": 251.2,
    "vehicle_status": "standby",
    "actual_kwh": 11,
    "max_usage": 10,
    "max_offline": 7,
    "smartcharging_max_usage": 6,
    "current_left": 10,
}

charge_point_status_timestamps = {
    "start_datetime": datetime.strptime("20211118 14:12:23+08:00", "%Y%m%d %H:%M:%S%z"),
    "stop_datetime": datetime.strptime("20211118 14:32:23+00:00", "%Y%m%d %H:%M:%S%z"),
    "offline_since": datetime.strptime("20211118 14:32:23+00:00", "%Y%m%d %H:%M:%S%z"),
}

charge_point_entity_ids = {
    "voltage_phase_1": "actual_v1",
    "voltage_phase_2": "actual_v2",
    "voltage_phase_3": "actual_v3",
    "current_phase_1": "actual_p1",
    "current_phase_2": "actual_p2",
    "current_phase_3": "actual_p3",
    "activity": "activity",
    "total_cost": "total_cost",
    "average_current": "avg_current",
    "average_voltage": "avg_voltage",
    "total_power": "total_kw",
    "vehicle_status": "vehicle_status",
    "energy_usage": "actual_kwh",
    "max_usage": "max_usage",
    "offline_max_usage": "max_offline",
    "smart_charging_max_usage": "smartcharging_max_usage",
    "remaining_current": "current_left",
}

charge_point_timestamp_entity_ids = {
    "started_on": "start_datetime",
    "stopped_on": "stop_datetime",
    "offline_since": "offline_since",
}

grid = {
    "grid_actual_p1": 12,
    "grid_actual_p2": 14,
    "grid_actual_p3": 15,
    "grid_max_current": 15,
    "grid_avg_current": 13.7,
}

grid_entity_ids = {
    "grid_current_phase_1": "grid_actual_p1",
    "grid_current_phase_2": "grid_actual_p2",
    "grid_current_phase_3": "grid_actual_p3",
    "max_grid_current": "grid_max_current",
    "average_grid_current": "grid_avg_current",
}


async def test_sensors_created(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test if all sensors are created."""
    await init_integration(
        hass,
        config_entry,
        "sensor",
        charge_point,
        charge_point_status | charge_point_status_timestamps,
        grid,
    )

    entity_registry = er.async_get(hass)

    sensors = er.async_entries_for_config_entry(entity_registry, "uuid")
    assert len(charge_point_status) + len(charge_point_status_timestamps) + len(
        grid
    ) == len(sensors)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test the underlying sensors."""
    await init_integration(
        hass, config_entry, "sensor", charge_point, charge_point_status, grid
    )

    entity_registry = er.async_get(hass)
    for entity_id, key in charge_point_entity_ids.items():
        entry = entity_registry.async_get(f"sensor.101_{entity_id}")
        assert entry
        assert entry.unique_id == f"{key}_101"

        state = hass.states.get(f"sensor.101_{entity_id}")
        assert state is not None

        value = charge_point_status[key]
        assert state.state == str(value)

    for entity_id, key in grid_entity_ids.items():
        entry = entity_registry.async_get(f"sensor.{entity_id}")
        assert entry
        assert entry.unique_id == key

        state = hass.states.get(f"sensor.{entity_id}")
        assert state is not None
        assert state.state == str(grid[key])


async def test_timestamp_sensors(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the underlying sensors."""
    await init_integration(
        hass, config_entry, "sensor", status=charge_point_status_timestamps
    )

    entity_registry = er.async_get(hass)
    for entity_id, key in charge_point_timestamp_entity_ids.items():
        entry = entity_registry.async_get(f"sensor.101_{entity_id}")
        assert entry
        assert entry.unique_id == f"{key}_101"

        state = hass.states.get(f"sensor.101_{entity_id}")
        assert state is not None

        value = charge_point_status_timestamps[key]
        assert datetime.strptime(state.state, "%Y-%m-%dT%H:%M:%S%z") == value


async def test_sensor_update(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test if the sensors get updated when there is new data."""
    client, _, _ = await init_integration(
        hass,
        config_entry,
        "sensor",
        status=charge_point_status | charge_point_status_timestamps,
        grid=grid,
    )

    await client.receiver(
        {
            "object": "CH_STATUS",
            "data": {
                "evse_id": "101",
                "avg_voltage": 20,
                "start_datetime": None,
                "actual_kwh": None,
            },
        }
    )
    await hass.async_block_till_done()

    await client.receiver(
        {
            "object": "GRID_STATUS",
            "data": {"grid_avg_current": 20},
        }
    )
    await hass.async_block_till_done()

    # test data updated
    state = hass.states.get("sensor.101_average_voltage")
    assert state is not None
    assert state.state == str(20)

    # grid
    state = hass.states.get("sensor.average_grid_current")
    assert state
    assert state.state == str(20)

    # test unavailable
    state = hass.states.get("sensor.101_energy_usage")
    assert state
    assert state.state == "unavailable"

    # test if timestamp keeps old value
    state = hass.states.get("sensor.101_started_on")
    assert state
    assert (
        datetime.strptime(state.state, "%Y-%m-%dT%H:%M:%S%z")
        == charge_point_status_timestamps["start_datetime"]
    )

    # test if older timestamp is ignored
    await client.receiver(
        {
            "object": "CH_STATUS",
            "data": {
                "evse_id": "101",
                "start_datetime": datetime.strptime(
                    "20211118 14:11:23+08:00", "%Y%m%d %H:%M:%S%z"
                ),
            },
        }
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.101_started_on")
    assert state
    assert (
        datetime.strptime(state.state, "%Y-%m-%dT%H:%M:%S%z")
        == charge_point_status_timestamps["start_datetime"]
    )
