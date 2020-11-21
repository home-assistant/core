"""Pytest module configuration."""
import pytest

from .common import build_device_mock

from tests.async_mock import patch


@pytest.fixture(autouse=True, name="device")
def device_fixture():
    """Path the device search and bind."""
    with patch(
        "homeassistant.components.gree.Device",
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
