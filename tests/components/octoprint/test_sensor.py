"""The tests for Octoptint binary sensor module."""
from datetime import datetime
from unittest.mock import patch

from . import init_integration


async def test_sensors(hass):
    """Test the underlying sensors."""
    printer = {
        "state": {
            "flags": {},
            "text": "Operational",
        },
        "temperature": {"tool1": {"actual": 18.83136, "target": 37.83136}},
    }
    job = {
        "job": {},
        "progress": {"completion": 50, "printTime": 600, "printTimeLeft": 6000},
        "state": "Printing",
    }
    with patch(
        "homeassistant.util.dt.utcnow", return_value=datetime(2020, 2, 20, 9, 10, 0)
    ):
        await init_integration(hass, "sensor", printer=printer, job=job)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    state = hass.states.get("sensor.octoprint_job_percentage")
    assert state is not None
    assert state.state == "50"
    assert state.name == "Octoprint Job Percentage"
    entry = entity_registry.async_get("sensor.octoprint_job_percentage")
    assert entry.unique_id == "Job Percentage-uuid"

    state = hass.states.get("sensor.octoprint_current_state")
    assert state is not None
    assert state.state == "Operational"
    assert state.name == "Octoprint Current State"
    entry = entity_registry.async_get("sensor.octoprint_current_state")
    assert entry.unique_id == "Current State-uuid"

    state = hass.states.get("sensor.octoprint_actual_tool1_temp")
    assert state is not None
    assert state.state == "18.83"
    assert state.name == "Octoprint actual tool1 temp"
    entry = entity_registry.async_get("sensor.octoprint_actual_tool1_temp")
    assert entry.unique_id == "actual tool1 temp-uuid"

    state = hass.states.get("sensor.octoprint_target_tool1_temp")
    assert state is not None
    assert state.state == "37.83"
    assert state.name == "Octoprint target tool1 temp"
    entry = entity_registry.async_get("sensor.octoprint_target_tool1_temp")
    assert entry.unique_id == "target tool1 temp-uuid"

    state = hass.states.get("sensor.octoprint_target_tool1_temp")
    assert state is not None
    assert state.state == "37.83"
    assert state.name == "Octoprint target tool1 temp"
    entry = entity_registry.async_get("sensor.octoprint_target_tool1_temp")
    assert entry.unique_id == "target tool1 temp-uuid"

    state = hass.states.get("sensor.octoprint_start_time")
    assert state is not None
    assert state.state == "2020-02-20T09:00:00"
    assert state.name == "Octoprint Start Time"
    entry = entity_registry.async_get("sensor.octoprint_start_time")
    assert entry.unique_id == "Start Time-uuid"

    state = hass.states.get("sensor.octoprint_estimated_finish_time")
    assert state is not None
    assert state.state == "2020-02-20T10:50:00"
    assert state.name == "Octoprint Estimated Finish Time"
    entry = entity_registry.async_get("sensor.octoprint_estimated_finish_time")
    assert entry.unique_id == "Estimated Finish Time-uuid"
