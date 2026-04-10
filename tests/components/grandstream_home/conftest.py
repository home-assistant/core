"""Common fixtures for Grandstream Home tests."""

from __future__ import annotations

from collections.abc import Generator
import datetime
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_socket import enable_socket

from homeassistant.components.grandstream_home.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry

_original_get_time_zone = dt_util.get_time_zone


def _get_time_zone(name):
    if name == "US/Pacific":
        return datetime.UTC
    return _original_get_time_zone(name)


@pytest.fixture(autouse=True)
def patch_dt_get_time_zone(monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
    """Patch dt_util.get_time_zone for tests and restore it afterwards."""
    monkeypatch.setattr(dt_util, "get_time_zone", _get_time_zone)
    return


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable custom integrations for all tests."""
    return


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.grandstream_home.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_gds_api():
    """Mock GDS API."""
    with patch("grandstream_home_api.GDSPhoneAPI") as mock_api:
        api_instance = MagicMock()
        api_instance.authenticate.return_value = True
        api_instance.get_phone_status.return_value = {
            "response": "success",
            "body": "idle",
        }
        api_instance.device_mac = "00:0B:82:12:34:56"
        api_instance.version = "1.0.0"
        mock_api.return_value = api_instance
        yield api_instance


@pytest.fixture
def mock_gns_api():
    """Mock GNS API."""
    with patch("grandstream_home_api.GNSNasAPI") as mock_api:
        api_instance = MagicMock()
        api_instance.authenticate.return_value = True
        api_instance.get_system_metrics.return_value = {
            "cpu_usage": 25.5,
            "memory_usage_percent": 45.2,
            "system_temperature": 35.0,
            "device_status": "online",
        }
        api_instance.device_mac = "00:0B:82:12:34:57"
        api_instance.version = "2.0.0"
        mock_api.return_value = api_instance
        yield api_instance


@pytest.fixture
def mock_config_entry():
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test Device",
        data={
            "host": "192.168.1.100",
            "username": "admin",
            "password": "password",
            "device_type": "GDS",
            "port": 80,
            "use_https": False,
        },
        entry_id="test_entry_id",
    )


@pytest.fixture
def mock_gds_entry():
    """Mock GDS config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test GDS Device",
        data={
            "host": "192.168.1.100",
            "username": "admin",
            "password": "password",
            "device_type": "GDS",
            "port": 80,
            "use_https": False,
        },
        entry_id="test_gds_entry_id",
    )


@pytest.fixture
def mock_gns_entry():
    """Mock GNS config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test GNS Device",
        data={
            "host": "192.168.1.101",
            "username": "admin",
            "password": "password",
            "device_type": "GNS",
            "port": 80,
            "use_https": False,
        },
        entry_id="test_gns_entry_id",
    )


@pytest.fixture
def mock_hass():
    """Mock Home Assistant."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {DOMAIN: {}}
    return hass


@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    """Configure pytest for Windows socket handling."""
    if sys.platform == "win32":
        config.__socket_force_enabled = True


@pytest.hookimpl(trylast=True)
def pytest_runtest_setup(item):
    """Enable socket for receiver tests on Windows."""
    if sys.platform == "win32" and str(item.fspath).endswith("test_receiver.py"):
        enable_socket()


@pytest.hookimpl(hookwrapper=True)
def pytest_fixture_setup(fixturedef, request):
    """Enable socket for event_loop fixture on Windows."""
    if sys.platform == "win32" and fixturedef.argname == "event_loop":
        enable_socket()
    yield
