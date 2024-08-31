"""Fixtures for PrusaLink."""
from unittest.mock import patch

import pytest

from homeassistant.components.prusalink import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry(hass):
    """Mock a PrusaLink config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "http://example.com", "username": "dummy", "password": "dummypw"},
        version=1,
        minor_version=2,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_version_api(hass):
    """Mock PrusaLink version API."""
    resp = {
        "api": "2.0.0",
        "server": "2.1.2",
        "text": "PrusaLink",
        "hostname": "PrusaXL",
    }
    with patch("pyprusalink.PrusaLink.get_version", return_value=resp):
        yield resp


@pytest.fixture
def mock_info_api(hass):
    """Mock PrusaLink info API."""
    resp = {
        "nozzle_diameter": 0.40,
        "mmu": False,
        "serial": "serial-1337",
        "hostname": "PrusaXL",
        "min_extrusion_temp": 170,
    }
    with patch("pyprusalink.PrusaLink.get_info", return_value=resp):
        yield resp


@pytest.fixture
def mock_get_legacy_printer(hass):
    """Mock PrusaLink printer API."""
    resp = {"telemetry": {"material": "PLA"}}
    with patch("pyprusalink.PrusaLink.get_legacy_printer", return_value=resp):
        yield resp


@pytest.fixture
def mock_get_status_idle(hass):
    """Mock PrusaLink printer API."""
    resp = {
        "storage": {
            "path": "/usb/",
            "name": "usb",
            "read_only": False,
        },
        "printer": {
            "state": "IDLE",
            "temp_bed": 41.9,
            "target_bed": 60.5,
            "temp_nozzle": 47.8,
            "target_nozzle": 210.1,
            "axis_z": 1.8,
            "axis_x": 7.9,
            "axis_y": 8.4,
            "flow": 100,
            "speed": 100,
            "fan_hotend": 100,
            "fan_print": 75,
        },
    }
    with patch("pyprusalink.PrusaLink.get_status", return_value=resp):
        yield resp


@pytest.fixture
def mock_get_status_printing(hass):
    """Mock PrusaLink printer API."""
    resp = {
        "job": {
            "id": 129,
            "progress": 37.00,
            "time_remaining": 73020,
            "time_printing": 43987,
        },
        "storage": {"path": "/usb/", "name": "usb", "read_only": False},
        "printer": {
            "state": "PRINTING",
            "temp_bed": 53.9,
            "target_bed": 85.0,
            "temp_nozzle": 6.0,
            "target_nozzle": 0.0,
            "axis_z": 5.0,
            "flow": 100,
            "speed": 100,
            "fan_hotend": 5000,
            "fan_print": 2500,
        },
    }
    with patch("pyprusalink.PrusaLink.get_status", return_value=resp):
        yield resp


@pytest.fixture
def mock_job_api_idle(hass):
    """Mock PrusaLink job API having no job."""
    resp = {}
    with patch("pyprusalink.PrusaLink.get_job", return_value=resp):
        yield resp


@pytest.fixture
def mock_job_api_printing(hass):
    """Mock PrusaLink printing."""
    resp = {
        "id": 129,
        "state": "PRINTING",
        "progress": 37.00,
        "time_remaining": 73020,
        "time_printing": 43987,
        "file": {
            "refs": {
                "icon": "/thumb/s/usb/TabletStand3~4.BGC",
                "thumbnail": "/thumb/l/usb/TabletStand3~4.BGC",
                "download": "/usb/TabletStand3~4.BGC",
            },
            "name": "TabletStand3~4.BGC",
            "display_name": "TabletStand3.bgcode",
            "path": "/usb",
            "size": 754535,
            "m_timestamp": 1698686881,
        },
    }
    with patch("pyprusalink.PrusaLink.get_job", return_value=resp):
        yield resp


@pytest.fixture
def mock_job_api_paused(hass, mock_get_status_printing, mock_job_api_printing):
    """Mock PrusaLink paused printing."""
    mock_job_api_printing["state"] = "PAUSED"
    mock_get_status_printing["printer"]["state"] = "PAUSED"


@pytest.fixture
def mock_api(
    mock_version_api,
    mock_info_api,
    mock_get_legacy_printer,
    mock_get_status_idle,
    mock_job_api_idle,
):
    """Mock PrusaLink API."""
