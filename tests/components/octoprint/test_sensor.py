"""The tests for Octoptint binary sensor module."""

from datetime import UTC, datetime

from freezegun.api import FrozenDateTimeFactory

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration


async def test_sensors(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the underlying sensors."""
    printer = {
        "state": {
            "flags": {"printing": True},
            "text": "Operational",
        },
        "temperature": {"tool1": {"actual": 18.83136, "target": 37.83136}},
    }
    job = __standard_job()
    freezer.move_to(datetime(2020, 2, 20, 9, 10, 13, 543, tzinfo=UTC))
    await init_integration(hass, "sensor", printer=printer, job=job)

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

    state = hass.states.get("sensor.octoprint_current_file")
    assert state is not None
    assert state.state == "Test_File_Name.gcode"
    assert state.name == "OctoPrint Current File"
    entry = entity_registry.async_get("sensor.octoprint_current_file")
    assert entry.unique_id == "Current File-uuid"

    state = hass.states.get("sensor.octoprint_current_file_size")
    assert state is not None
    assert state.state == "123.456789"
    assert state.attributes.get("unit_of_measurement") == UnitOfInformation.MEGABYTES
    assert state.name == "OctoPrint Current File Size"
    entry = entity_registry.async_get("sensor.octoprint_current_file_size")
    assert entry.unique_id == "Current File Size-uuid"


async def test_sensors_no_target_temp(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
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

    state = hass.states.get("sensor.octoprint_actual_tool1_temp")
    assert state is not None
    assert state.state == "18.83"
    assert state.name == "OctoPrint actual tool1 temp"
    entry = entity_registry.async_get("sensor.octoprint_actual_tool1_temp")
    assert entry.unique_id == "actual tool1 temp-uuid"

    state = hass.states.get("sensor.octoprint_target_tool1_temp")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.name == "OctoPrint target tool1 temp"
    entry = entity_registry.async_get("sensor.octoprint_target_tool1_temp")
    assert entry.unique_id == "target tool1 temp-uuid"

    state = hass.states.get("sensor.octoprint_current_file")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert state.name == "OctoPrint Current File"
    entry = entity_registry.async_get("sensor.octoprint_current_file")
    assert entry.unique_id == "Current File-uuid"

    state = hass.states.get("sensor.octoprint_current_file_size")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert state.name == "OctoPrint Current File Size"
    entry = entity_registry.async_get("sensor.octoprint_current_file_size")
    assert entry.unique_id == "Current File Size-uuid"


async def test_sensors_paused(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the underlying sensors."""
    printer = {
        "state": {
            "flags": {"printing": False},
            "text": "Operational",
        },
        "temperature": {"tool1": {"actual": 18.83136, "target": None}},
    }
    job = __standard_job()
    freezer.move_to(datetime(2020, 2, 20, 9, 10, 0))
    await init_integration(hass, "sensor", printer=printer, job=job)

    state = hass.states.get("sensor.octoprint_start_time")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.name == "OctoPrint Start Time"
    entry = entity_registry.async_get("sensor.octoprint_start_time")
    assert entry.unique_id == "Start Time-uuid"

    state = hass.states.get("sensor.octoprint_estimated_finish_time")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.name == "OctoPrint Estimated Finish Time"
    entry = entity_registry.async_get("sensor.octoprint_estimated_finish_time")
    assert entry.unique_id == "Estimated Finish Time-uuid"


async def test_sensors_printer_disconnected(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the underlying sensors."""
    job = __standard_job()
    freezer.move_to(datetime(2020, 2, 20, 9, 10, 0))
    await init_integration(hass, "sensor", printer=None, job=job)

    state = hass.states.get("sensor.octoprint_job_percentage")
    assert state is not None
    assert state.state == "50"
    assert state.name == "OctoPrint Job Percentage"
    entry = entity_registry.async_get("sensor.octoprint_job_percentage")
    assert entry.unique_id == "Job Percentage-uuid"

    state = hass.states.get("sensor.octoprint_current_state")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert state.name == "OctoPrint Current State"
    entry = entity_registry.async_get("sensor.octoprint_current_state")
    assert entry.unique_id == "Current State-uuid"

    state = hass.states.get("sensor.octoprint_start_time")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.name == "OctoPrint Start Time"
    entry = entity_registry.async_get("sensor.octoprint_start_time")
    assert entry.unique_id == "Start Time-uuid"

    state = hass.states.get("sensor.octoprint_estimated_finish_time")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.name == "OctoPrint Estimated Finish Time"
    entry = entity_registry.async_get("sensor.octoprint_estimated_finish_time")
    assert entry.unique_id == "Estimated Finish Time-uuid"


def __standard_job():
    return {
        "job": {
            "averagePrintTime": 6500,
            "estimatedPrintTime": 6000,
            "filament": {"tool0": {"length": 3000, "volume": 7}},
            "file": {
                "date": 1577836800,
                "display": "Test File Name",
                "name": "Test_File_Name.gcode",
                "origin": "local",
                "path": "Folder1/Folder2/Test_File_Name.gcode",
                "size": 123456789,
            },
            "lastPrintTime": 12345.678,
            "user": "testUser",
        },
        "progress": {"completion": 50, "printTime": 600, "printTimeLeft": 6000},
        "state": "Printing",
    }
