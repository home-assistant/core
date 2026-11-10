"""Tests for the OctoPrint diagnostics."""

from typing import Any

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant


@pytest.fixture
def platform() -> Platform:
    """Fixture to specify platform."""
    return Platform.SENSOR


@pytest.fixture
def job() -> dict[str, Any]:
    """Job fixture."""
    return {
        "job": {
            "averagePrintTime": None,
            "estimatedPrintTime": 4200,
            "filament": None,
            "file": {
                "date": None,
                "display": "secret_model.gcode",
                "name": "secret_model.gcode",
                "origin": "local",
                "path": "folder/secret_model.gcode",
                "size": 123456,
            },
            "lastPrintTime": None,
            "user": "octouser",
        },
        "progress": {"completion": 50, "printTime": 600, "printTimeLeft": 6000},
        "state": "Printing",
    }


@pytest.fixture
def printer() -> dict[str, Any]:
    """Printer fixture."""
    return {
        "state": {
            "flags": {"printing": True, "error": False, "operational": True},
            "text": "Printing",
        },
        "temperature": {
            "bed": {"actual": 60.1, "target": 60.0, "offset": 0},
            "tool0": {"actual": 210.5, "target": 210.0, "offset": 0},
        },
    }


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
        == snapshot
    )
