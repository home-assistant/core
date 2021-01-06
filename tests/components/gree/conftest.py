"""Pytest module configuration."""
from unittest.mock import AsyncMock, patch

import pytest

from .common import build_device_info_mock, build_device_mock


@pytest.fixture(name="discovery")
def discovery_fixture():
    """Patch the discovery service."""
    with patch(
        "homeassistant.components.gree.bridge.Discovery.search_devices",
        new_callable=AsyncMock,
        return_value=[build_device_info_mock()],
    ) as mock:
        yield mock


@pytest.fixture(name="device")
def device_fixture():
    """Path the device search and bind."""
    with patch(
        "homeassistant.components.gree.bridge.Device",
        return_value=build_device_mock(),
    ) as mock:
        yield mock


@pytest.fixture(name="setup")
def setup_fixture():
    """Patch the climate setup."""
    with patch(
        "homeassistant.components.gree.climate.async_setup_entry", return_value=True
    ) as setup:
        yield setup
