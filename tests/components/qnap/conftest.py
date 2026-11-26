"""Setup the QNAP tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.qnap.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

TEST_HOST = "1.2.3.4"
TEST_USERNAME = "admin"
TEST_PASSWORD = "password"
TEST_NAS_NAME = "Test NAS name"
TEST_SERIAL = "123456789"

TEST_SYSTEM_STATS = {"system": {"serial_number": TEST_SERIAL, "name": TEST_NAS_NAME}}

TEST_FULL_SYSTEM_STATS = {
    "system": {
        "name": TEST_NAS_NAME,
        "model": "TS-453D",
        "serial_number": TEST_SERIAL,
        "temp_c": 40,
        "temp_f": 104,
        "timezone": "Europe/Stockholm",
    },
    "firmware": {
        "version": "5.2.0",
        "build": "20240813",
        "patch": "0",
        "build_time": "2024/08/13",
    },
    "uptime": {"days": 1, "hours": 2, "minutes": 3, "seconds": 4},
    "cpu": {
        "model": "Intel Celeron",
        "usage_percent": 5.2,
        "temp_c": 45,
        "temp_f": 113,
    },
    "memory": {"total": 7820.0, "free": 3910.0},
    "nics": {
        "eth0": {
            "link_status": "Up",
            "max_speed": 2500,
            "ip": TEST_HOST,
            "mask": "255.255.255.0",
            "mac": "00:08:9b:aa:bb:cc",
            "usage": "1",
            "rx_packets": 1000,
            "tx_packets": 2000,
            "err_packets": 0,
        }
    },
    "dns": ["1.1.1.1"],
    "sysfans": {"sysfan0": {"speed": 800, "status": "ok"}},
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.qnap.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def qnap_connect() -> Generator[MagicMock]:
    """Mock qnap connection."""
    with patch(
        "homeassistant.components.qnap.config_flow.QNAPStats", autospec=True
    ) as host_mock_class:
        host_mock = host_mock_class.return_value
        host_mock.get_system_stats.return_value = TEST_SYSTEM_STATS
        yield host_mock


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a QNAP config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=TEST_NAS_NAME,
        unique_id=TEST_SERIAL,
        data={
            CONF_HOST: TEST_HOST,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
            CONF_VERIFY_SSL: True,
            CONF_PORT: 8080,
        },
    )


@pytest.fixture
def mock_qnap_api() -> Generator[MagicMock]:
    """Mock the QNAP API used by the coordinator."""
    with patch(
        "homeassistant.components.qnap.coordinator.QNAPStats", autospec=True
    ) as api_class:
        api = api_class.return_value
        api.get_system_stats.return_value = TEST_FULL_SYSTEM_STATS
        api.get_system_health.return_value = "good"
        api.get_smart_disk_health.return_value = {
            "1": {
                "drive_number": "1",
                "health": "OK",
                "temp_c": 35,
                "temp_f": 95,
                "capacity": "3.64 TB",
                "model": "WD40EFRX",
                "serial": "WD-WCC4E1234567",
                "type": "hdd",
            }
        }
        api.get_volumes.return_value = {
            "DataVol1": {
                "id": "1",
                "label": "DataVol1",
                "free_size": 1000000000,
                "total_size": 4000000000,
                "folders": [{"sharename": "Public", "used_size": 1000}],
            }
        }
        api.get_bandwidth.return_value = {
            "eth0": {"name": "Adapter 1", "rx": 100, "tx": 200, "is_default": True}
        }
        yield api
