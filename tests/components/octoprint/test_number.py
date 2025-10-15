"""The tests for OctoPrint number module."""

from datetime import UTC, datetime
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import snapshot_platform


async def test_numbers(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the underlying number entities."""
    printer = {
        "state": {
            "flags": {"printing": True},
            "text": "Operational",
        },
        "temperature": {
            "tool0": {"actual": 18.83136, "target": 37.83136},
            "tool1": {"actual": 21.0, "target": 31.0},
            "bed": {"actual": 25.5, "target": 60.0},
        },
    }
    job = __standard_job()
    freezer.move_to(datetime(2020, 2, 20, 9, 10, 13, 543, tzinfo=UTC))
    config_entry = await init_integration(hass, "number", printer=printer, job=job)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


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
            "bed": {"actual": 25.5, "target": None},
        },
    }
    freezer.move_to(datetime(2020, 2, 20, 9, 10, 0))
    await init_integration(hass, "number", printer=printer)

    state = hass.states.get("number.octoprint_extruder_temperature")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.name == "OctoPrint Extruder temperature"
    entry = entity_registry.async_get("number.octoprint_extruder_temperature")
    assert entry.unique_id == "uuid_tool0_temperature"

    state = hass.states.get("number.octoprint_bed_temperature")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.name == "OctoPrint Bed temperature"
    entry = entity_registry.async_get("number.octoprint_bed_temperature")
    assert entry.unique_id == "uuid_bed_temperature"


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
        entity_component = hass.data[NUMBER_DOMAIN]

        entity = entity_component.get_entity("number.octoprint_extruder_temperature")
        assert entity is not None

        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity.entity_id, ATTR_VALUE: 200.4},
            blocking=True,
        )
        assert len(mock_set_tool_temp.mock_calls) == 1
        # Verify that we pass integer, expected by the pyoctoprintapi
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
        entity_component = hass.data[NUMBER_DOMAIN]
        entity = entity_component.get_entity("number.octoprint_bed_temperature")
        assert entity is not None

        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity.entity_id, ATTR_VALUE: 80.6},
            blocking=True,
        )

        assert len(mock_set_bed_temp.mock_calls) == 1
        # Verify that we pass integer, expected by the pyoctoprintapi, and that it's rounded down
        mock_set_bed_temp.assert_called_with(80)


async def test_set_tool_n_temp(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setting tool temperature via number entity when multiple tools are present."""
    printer = {
        "state": {
            "flags": {"printing": False},
            "text": "Operational",
        },
        "temperature": {
            "tool0": {"actual": 20.0, "target": 30.0},
            "tool1": {"actual": 21.0, "target": 31.0}
        },
    }
    job = __standard_job()
    freezer.move_to(datetime(2020, 2, 20, 9, 10, 0))
    await init_integration(hass, "number", printer=printer, job=job)

    with patch(
        "pyoctoprintapi.OctoprintClient.set_tool_temperature"
    ) as mock_set_tool_temp:
        entity_component = hass.data[NUMBER_DOMAIN]

        entity = entity_component.get_entity("number.octoprint_extruder_1_temperature")
        assert entity is not None

        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity.entity_id, ATTR_VALUE: 41.0},
            blocking=True,
        )
        assert len(mock_set_tool_temp.mock_calls) == 1
        # Verify that we pass integer, expected by the pyoctoprintapi
        mock_set_tool_temp.assert_called_with("tool1", 41)


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
    state = hass.states.get("number.octoprint_tool0_temperature")
    assert state is None

    state = hass.states.get("number.octoprint_bed_temperature")
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
