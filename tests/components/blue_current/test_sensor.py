"""The tests for Blue current sensors."""
from datetime import datetime
from typing import Any

from homeassistant.components.blue_current import Connector
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from . import init_integration

TIMESTAMP_KEYS = ("start_datetime", "stop_datetime", "offline_since")


charge_point = {
    "actual_v1": 14,
    "actual_v2": 18,
    "actual_v3": 15,
    "actual_p1": 19,
    "actual_p2": 14,
    "actual_p3": 15,
    "activity": "available",
    "start_datetime": datetime.strptime("20211118 14:12:23+08:00", "%Y%m%d %H:%M:%S%z"),
    "stop_datetime": datetime.strptime("20211118 14:32:23+00:00", "%Y%m%d %H:%M:%S%z"),
    "offline_since": datetime.strptime("20211118 14:32:23+00:00", "%Y%m%d %H:%M:%S%z"),
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

data: dict[str, Any] = {
    "101": {
        "model_type": "hidden",
        "evse_id": "101",
        "name": "",
        **charge_point,
    }
}


charge_point_entity_ids = {
    "voltage_phase_1": "actual_v1",
    "voltage_phase_2": "actual_v2",
    "voltage_phase_3": "actual_v3",
    "current_phase_1": "actual_p1",
    "current_phase_2": "actual_p2",
    "current_phase_3": "actual_p3",
    "activity": "activity",
    "started_on": "start_datetime",
    "stopped_on": "stop_datetime",
    "offline_since": "offline_since",
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


async def test_sensors(hass: HomeAssistant) -> None:
    """Test the underlying sensors."""
    await init_integration(hass, "sensor", data, grid)

    entity_registry = er.async_get(hass)
    for entity_id, key in charge_point_entity_ids.items():
        entry = entity_registry.async_get(f"sensor.101_{entity_id}")
        assert entry
        assert entry.unique_id == f"{key}_101"

        # skip sensors that are disabled by default.
        if not entry.disabled:
            state = hass.states.get(f"sensor.101_{entity_id}")
            assert state is not None

            value = charge_point[key]

            if key in TIMESTAMP_KEYS:
                assert datetime.strptime(state.state, "%Y-%m-%dT%H:%M:%S%z") == value
            else:
                assert state.state == str(value)

    for entity_id, key in grid_entity_ids.items():
        entry = entity_registry.async_get(f"sensor.{entity_id}")
        assert entry
        assert entry.unique_id == key

        # skip sensors that are disabled by default.
        if not entry.disabled:
            state = hass.states.get(f"sensor.{entity_id}")
            assert state is not None
            assert state.state == str(grid[key])

    sensors = er.async_entries_for_config_entry(entity_registry, "uuid")
    assert len(charge_point.keys()) + len(grid.keys()) == len(sensors)


async def test_sensor_update(hass: HomeAssistant) -> None:
    """Test if the sensors get updated when there is new data."""
    await init_integration(hass, "sensor", data, grid)
    key = "avg_voltage"
    entity_id = "average_voltage"
    timestamp_key = "start_datetime"
    timestamp_entity_id = "started_on"
    grid_key = "grid_avg_current"
    grid_entity_id = "average_grid_current"

    connector: Connector = hass.data["blue_current"]["uuid"]

    connector.charge_points = {"101": {key: 20, timestamp_key: None}}
    connector.grid = {grid_key: 20}
    async_dispatcher_send(hass, "blue_current_value_update_101")
    await hass.async_block_till_done()
    async_dispatcher_send(hass, "blue_current_grid_update")
    await hass.async_block_till_done()

    # test data updated
    state = hass.states.get(f"sensor.101_{entity_id}")
    assert state is not None
    assert state.state == str(20)

    # grid
    state = hass.states.get(f"sensor.{grid_entity_id}")
    assert state
    assert state.state == str(20)

    # test unavailable
    state = hass.states.get("sensor.101_energy_usage")
    assert state
    assert state.state == "unavailable"

    # test if timestamp keeps old value
    state = hass.states.get(f"sensor.101_{timestamp_entity_id}")
    assert state
    assert (
        datetime.strptime(state.state, "%Y-%m-%dT%H:%M:%S%z")
        == charge_point[timestamp_key]
    )

    # test if older timestamp is ignored
    connector.charge_points = {
        "101": {
            timestamp_key: datetime.strptime(
                "20211118 14:11:23+08:00", "%Y%m%d %H:%M:%S%z"
            )
        }
    }
    async_dispatcher_send(hass, "blue_current_value_update_101")
    state = hass.states.get(f"sensor.101_{timestamp_entity_id}")
    assert state
    assert (
        datetime.strptime(state.state, "%Y-%m-%dT%H:%M:%S%z")
        == charge_point[timestamp_key]
    )
