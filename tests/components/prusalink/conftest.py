"""Fixtures for PrusaLink."""

from unittest.mock import patch

import pytest

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry(hass):
    """Mock a PrusaLink config entry."""
    entry = MockConfigEntry(
        domain="prusalink", data={"host": "http://example.com", "api_key": "abcdefgh"}
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_version_api(hass):
    """Mock PrusaLink version API."""
    resp = {
        "api": "2.0.0",
        "server": "2.1.2",
        "text": "PrusaLink MINI",
        "hostname": "PrusaMINI",
    }
    with patch("pyprusalink.PrusaLink.get_version", return_value=resp):
        yield resp


@pytest.fixture
def mock_printer_api(hass):
    """Mock PrusaLink printer API."""
    resp = {
        "telemetry": {
            "temp-bed": 41.9,
            "temp-nozzle": 47.8,
            "print-speed": 100,
            "z-height": 1.8,
            "material": "PLA",
        },
        "temperature": {
            "tool0": {"actual": 47.8, "target": 210.1, "display": 0.0, "offset": 0},
            "bed": {"actual": 41.9, "target": 60.5, "offset": 0},
        },
        "state": {
            "text": "Operational",
            "flags": {
                "operational": True,
                "paused": False,
                "printing": False,
                "cancelling": False,
                "pausing": False,
                "sdReady": False,
                "error": False,
                "closedOnError": False,
                "ready": True,
                "busy": False,
            },
        },
    }
    with patch("pyprusalink.PrusaLink.get_printer", return_value=resp):
        yield resp


@pytest.fixture
def mock_job_api_idle(hass):
    """Mock PrusaLink job API having no job."""
    resp = {
        "state": "Operational",
        "job": None,
        "progress": None,
    }
    with patch("pyprusalink.PrusaLink.get_job", return_value=resp):
        yield resp


@pytest.fixture
def mock_job_api_printing(hass, mock_printer_api, mock_job_api_idle):
    """Mock PrusaLink printing."""
    mock_printer_api["state"]["text"] = "Printing"
    mock_printer_api["state"]["flags"]["printing"] = True

    mock_job_api_idle.update(
        {
            "state": "Printing",
            "job": {
                "estimatedPrintTime": 117007,
                "file": {
                    "name": "TabletStand3.gcode",
                    "path": "/usb/TABLET~1.GCO",
                    "display": "TabletStand3.gcode",
                },
            },
            "progress": {
                "completion": 0.37,
                "printTime": 43987,
                "printTimeLeft": 73020,
            },
        }
    )


@pytest.fixture
def mock_job_api_paused(hass, mock_printer_api, mock_job_api_idle):
    """Mock PrusaLink paused printing."""
    mock_printer_api["state"]["text"] = "Paused"
    mock_printer_api["state"]["flags"]["printing"] = False
    mock_printer_api["state"]["flags"]["paused"] = True

    mock_job_api_idle["state"] = "Paused"


@pytest.fixture
def mock_api(mock_version_api, mock_printer_api, mock_job_api_idle):
    """Mock PrusaLink API."""
