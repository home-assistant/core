"""The tests for OctoPrint number module."""

from datetime import UTC, datetime

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components import number
from unittest.mock import patch

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

async def test_numbers(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the underlying number entities."""
    printer = {
        "state": {
            "flags": {"printing": True},
            "text": "Operational",
        },
        "temperature": {
            "tool0": {"actual": 18.83136, "target": 37.83136},
            "bed": {"actual": 25.5, "target": 60.0},
        },
    }
    job = __standard_job()
    freezer.move_to(datetime(2020, 2, 20, 9, 10, 13, 543, tzinfo=UTC))
    await init_integration(hass, "number", printer=printer, job=job)

    state = hass.states.get("number.octoprint_set_tool0_temp")
    assert state is not None
    assert state.state == "37.83"
    assert state.name == "OctoPrint set tool0 temp"
    assert state.attributes.get("unit_of_measurement") == UnitOfTemperature.CELSIUS
    assert state.attributes.get("min") == 0
    assert state.attributes.get("max") == 300
    assert state.attributes.get("step") == 1
    entry = entity_registry.async_get("number.octoprint_set_tool0_temp")
    assert entry.unique_id == "set-tool0-temp-uuid"

    state = hass.states.get("number.octoprint_set_bed_temp")
    assert state is not None
    assert state.state == "60.0"
    assert state.name == "OctoPrint set bed temp"
    assert state.attributes.get("unit_of_measurement") == UnitOfTemperature.CELSIUS
    assert state.attributes.get("min") == 0
    assert state.attributes.get("max") == 300
    assert state.attributes.get("step") == 1
    entry = entity_registry.async_get("number.octoprint_set_bed_temp")
    assert entry.unique_id == "set-bed-temp-uuid"


async def test_numbers_no_target_temp(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the number entities when target temperature is None."""
    printer = {
        "state": {
            "flags": {"printing": True, "paused": False},
            "text": "Operational",
        },
        "temperature": {
            "tool0": {"actual": 18.83136, "target": None},
            "bed": {"actual": 25.5, "target": None}
        },
    }
    freezer.move_to(datetime(2020, 2, 20, 9, 10, 0))
    await init_integration(hass, "number", printer=printer)

    state = hass.states.get("number.octoprint_set_tool0_temp")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.name == "OctoPrint set tool0 temp"
    entry = entity_registry.async_get("number.octoprint_set_tool0_temp")
    assert entry.unique_id == "set-tool0-temp-uuid"

    state = hass.states.get("number.octoprint_set_bed_temp")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.name == "OctoPrint set bed temp"
    entry = entity_registry.async_get("number.octoprint_set_bed_temp")
    assert entry.unique_id == "set-bed-temp-uuid"


async def test_set_tool_temp(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setting tool temperature via number entity."""
    printer = {
        "state": {
            "flags": {"printing": False},
            "text": "Operational",
        },
        "temperature": {"tool0": {"actual": 18.83136, "target": 25.0}},
    }
    job = __standard_job()
    freezer.move_to(datetime(2020, 2, 20, 9, 10, 0))
    await init_integration(hass, "number", printer=printer, job=job)

    with patch(
        "pyoctoprintapi.OctoprintClient.set_tool_temperature"
    ) as mock_set_tool_temp:
        entity_component = hass.data[number.DOMAIN]
        entity = entity_component.get_entity("number.octoprint_set_tool0_temp")
        assert entity is not None

        await entity.async_set_native_value(200.0)

        assert len(mock_set_tool_temp.mock_calls) == 1
        # Verify that we pass int to the API
        mock_set_tool_temp.assert_called_with("tool0", 200)


async def test_set_bed_temp(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setting bed temperature via number entity."""
    printer = {
        "state": {
            "flags": {"printing": False},
            "text": "Operational",
        },
        "temperature": {"bed": {"actual": 20.0, "target": 50.0}},
    }
    job = __standard_job()
    freezer.move_to(datetime(2020, 2, 20, 9, 10, 0))
    await init_integration(hass, "number", printer=printer, job=job)

    with patch(
        "pyoctoprintapi.OctoprintClient.set_bed_temperature"
    ) as mock_set_bed_temp:
        entity_component = hass.data[number.DOMAIN]
        entity = entity_component.get_entity("number.octoprint_set_bed_temp")
        assert entity is not None

        await entity.async_set_native_value(80.0)

        assert len(mock_set_bed_temp.mock_calls) == 1
        # Verify that we pass int to the API
        mock_set_bed_temp.assert_called_with(80)


async def test_numbers_printer_disconnected(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test number entities when printer is disconnected."""
    job = __standard_job()
    freezer.move_to(datetime(2020, 2, 20, 9, 10, 0))
    await init_integration(hass, "number", printer=None, job=job)

    # When printer is disconnected, no number entities should be created
    state = hass.states.get("number.octoprint_set_tool0_temp")
    assert state is None

    state = hass.states.get("number.octoprint_set_bed_temp")
    assert state is None


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
