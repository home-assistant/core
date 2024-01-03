"""The tests for Octoptint binary sensor module."""
from datetime import UTC, datetime

from freezegun.api import FrozenDateTimeFactory

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration


async def test_sensors(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Test the underlying sensors."""
    printer = {
        "state": {
            "flags": {"printing": True},
            "text": "Operational",
        },
        "temperature": {"tool1": {"actual": 18.83136, "target": 37.83136}},
    }
    job = {
        "job": {},
        "progress": {"completion": 50, "printTime": 600, "printTimeLeft": 6000},
        "state": "Printing",
    }
    freezer.move_to(datetime(2020, 2, 20, 9, 10, 13, 543, tzinfo=UTC))
    await init_integration(hass, "sensor", printer=printer, job=job)

    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.octoprint_job_percentage")
    assert state is not None
    assert state.state == "50"
    assert state.name == "OctoPrint Job Percentage"
    entry = entity_registry.async_get("sensor.octoprint_job_percentage")
    assert entry.unique_id == "Job Percentage-uuid"

    state = hass.states.get("sensor.octoprint_current_state")
    assert state is not None
    assert state.state == "Operational"
    assert state.name == "OctoPrint Current State"
    entry = entity_registry.async_get("sensor.octoprint_current_state")
    assert entry.unique_id == "Current State-uuid"

    state = hass.states.get("sensor.octoprint_actual_tool1_temp")
    assert state is not None
    assert state.state == "18.83"
    assert state.name == "OctoPrint actual tool1 temp"
    entry = entity_registry.async_get("sensor.octoprint_actual_tool1_temp")
    assert entry.unique_id == "actual tool1 temp-uuid"

    state = hass.states.get("sensor.octoprint_target_tool1_temp")
    assert state is not None
    assert state.state == "37.83"
    assert state.name == "OctoPrint target tool1 temp"
    entry = entity_registry.async_get("sensor.octoprint_target_tool1_temp")
    assert entry.unique_id == "target tool1 temp-uuid"

    state = hass.states.get("sensor.octoprint_target_tool1_temp")
    assert state is not None
    assert state.state == "37.83"
    assert state.name == "OctoPrint target tool1 temp"
    entry = entity_registry.async_get("sensor.octoprint_target_tool1_temp")
    assert entry.unique_id == "target tool1 temp-uuid"

    state = hass.states.get("sensor.octoprint_start_time")
    assert state is not None
    assert state.state == "2020-02-20T09:00:00+00:00"
    assert state.name == "OctoPrint Start Time"
    entry = entity_registry.async_get("sensor.octoprint_start_time")
    assert entry.unique_id == "Start Time-uuid"

    state = hass.states.get("sensor.octoprint_estimated_finish_time")
    assert state is not None
    assert state.state == "2020-02-20T10:50:00+00:00"
    assert state.name == "OctoPrint Estimated Finish Time"
    entry = entity_registry.async_get("sensor.octoprint_estimated_finish_time")
    assert entry.unique_id == "Estimated Finish Time-uuid"


async def test_sensors_no_target_temp(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the underlying sensors."""
    printer = {
        "state": {
            "flags": {"printing": True, "paused": False},
            "text": "Operational",
        },
        "temperature": {"tool1": {"actual": 18.83136, "target": None}},
    }
    freezer.move_to(datetime(2020, 2, 20, 9, 10, 0))
    await init_integration(hass, "sensor", printer=printer)

    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.octoprint_actual_tool1_temp")
    assert state is not None
    assert state.state == "18.83"
    assert state.name == "OctoPrint actual tool1 temp"
    entry = entity_registry.async_get("sensor.octoprint_actual_tool1_temp")
    assert entry.unique_id == "actual tool1 temp-uuid"

    state = hass.states.get("sensor.octoprint_target_tool1_temp")
    assert state is not None
    assert state.state == "unknown"
    assert state.name == "OctoPrint target tool1 temp"
    entry = entity_registry.async_get("sensor.octoprint_target_tool1_temp")
    assert entry.unique_id == "target tool1 temp-uuid"


async def test_sensors_paused(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the underlying sensors."""
    printer = {
        "state": {
            "flags": {"printing": False},
            "text": "Operational",
        },
        "temperature": {"tool1": {"actual": 18.83136, "target": None}},
    }
    job = {
        "job": {},
        "progress": {"completion": 50, "printTime": 600, "printTimeLeft": 6000},
        "state": "Paused",
    }
    freezer.move_to(datetime(2020, 2, 20, 9, 10, 0))
    await init_integration(hass, "sensor", printer=printer, job=job)

    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.octoprint_start_time")
    assert state is not None
    assert state.state == "unknown"
    assert state.name == "OctoPrint Start Time"
    entry = entity_registry.async_get("sensor.octoprint_start_time")
    assert entry.unique_id == "Start Time-uuid"

    state = hass.states.get("sensor.octoprint_estimated_finish_time")
    assert state is not None
    assert state.state == "unknown"
    assert state.name == "OctoPrint Estimated Finish Time"
    entry = entity_registry.async_get("sensor.octoprint_estimated_finish_time")
    assert entry.unique_id == "Estimated Finish Time-uuid"


async def test_sensors_printer_disconnected(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the underlying sensors."""
    job = {
        "job": {},
        "progress": {"completion": 50, "printTime": 600, "printTimeLeft": 6000},
        "state": "Paused",
    }
    freezer.move_to(datetime(2020, 2, 20, 9, 10, 0))
    await init_integration(hass, "sensor", printer=None, job=job)

    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.octoprint_job_percentage")
    assert state is not None
    assert state.state == "50"
    assert state.name == "OctoPrint Job Percentage"
    entry = entity_registry.async_get("sensor.octoprint_job_percentage")
    assert entry.unique_id == "Job Percentage-uuid"

    state = hass.states.get("sensor.octoprint_current_state")
    assert state is not None
    assert state.state == "unavailable"
    assert state.name == "OctoPrint Current State"
    entry = entity_registry.async_get("sensor.octoprint_current_state")
    assert entry.unique_id == "Current State-uuid"

    state = hass.states.get("sensor.octoprint_start_time")
    assert state is not None
    assert state.state == "unknown"
    assert state.name == "OctoPrint Start Time"
    entry = entity_registry.async_get("sensor.octoprint_start_time")
    assert entry.unique_id == "Start Time-uuid"

    state = hass.states.get("sensor.octoprint_estimated_finish_time")
    assert state is not None
    assert state.state == "unknown"
    assert state.name == "OctoPrint Estimated Finish Time"
    entry = entity_registry.async_get("sensor.octoprint_estimated_finish_time")
    assert entry.unique_id == "Estimated Finish Time-uuid"
