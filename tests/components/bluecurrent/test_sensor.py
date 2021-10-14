"""The tests for Bluecurrent sensors."""
from datetime import datetime

from homeassistant.components.bluecurrent import Connector
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from . import init_integration

TIMESTAMP_KEYS = ("start_datetime", "stop_datetime", "offline_since")

data = {
    "101": {
        "model_type": "hidden",
        "evse_id": "101",
    }
}

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
    "vehicle_status": "offline",
    "actual_kwh": 11,
    "max_usage": 10,
    "max_offline": 7,
    "smartcharging_max_usage": 6,
    "current_left": 10,
}

grid = {
    "grid_actual_p1": 12,
    "grid_actual_p2": 14,
    "grid_actual_p3": 15,
    "grid_max_current": 15,
    "grid_avg_current": 13.7,
}


async def test_sensors(hass: HomeAssistant):
    """Test the underlying sensors."""
    await init_integration(hass, "sensor", data, charge_point, grid)

    entity_registry = er.async_get(hass)
    for key, value in charge_point.items():
        entry = entity_registry.async_get(f"sensor.{key}_101")
        assert entry
        assert entry.unique_id == f"{key}_101"

        # skip sensors that are disabled by default.
        if not entry.disabled:
            state = hass.states.get(f"sensor.{key}_101")
            assert state is not None

            if key in TIMESTAMP_KEYS:
                assert datetime.strptime(state.state, "%Y-%m-%dT%H:%M:%S%z") == value
            else:
                assert state.state == str(value)

    for key, value in grid.items():
        entry = entity_registry.async_get(f"sensor.{key}")
        assert entry
        assert entry.unique_id == key

        # skip sensors that are disabled by default.
        if not entry.disabled:
            state = hass.states.get(f"sensor.{key}")
            assert state is not None
            assert state.state == str(value)

    sensors = er.async_entries_for_config_entry(entity_registry, "uuid")
    assert len(charge_point.keys()) + len(grid.keys()) == len(sensors)


async def test_sensor_update(hass: HomeAssistant):
    """Test if the sensors get updated when there is new data."""
    await init_integration(hass, "sensor", data, charge_point, grid)
    key = "avg_voltage"
    timestamp_key = "start_datetime"
    grid_key = "grid_avg_current"

    connector: Connector = hass.data["bluecurrent"]["uuid"]

    connector.charge_points = {"101": {key: 20, timestamp_key: None}}
    connector.grid = {grid_key: 20}
    async_dispatcher_send(hass, "bluecurrent_value_update_101")
    async_dispatcher_send(hass, "bluecurrent_grid_update")

    # test data updated
    state = hass.states.get(f"sensor.{key}_101")
    assert state is not None
    assert state.state == str(20)

    # grid
    state = hass.states.get(f"sensor.{grid_key}")
    assert state
    assert state.state == str(20)

    # test unavailable
    state = hass.states.get("sensor.actual_kwh_101")
    assert state
    assert state.state == "unavailable"

    # test if timestamp keeps old value
    state = hass.states.get(f"sensor.{timestamp_key}_101")
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
    async_dispatcher_send(hass, "bluecurrent_value_update_101")
    state = hass.states.get(f"sensor.{timestamp_key}_101")
    assert state
    assert (
        datetime.strptime(state.state, "%Y-%m-%dT%H:%M:%S%z")
        == charge_point[timestamp_key]
    )
