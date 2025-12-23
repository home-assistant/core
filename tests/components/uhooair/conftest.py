"""Global fixtures for uHoo integration."""

from unittest.mock import patch

import pytest
from uhooapi import Device
from uhooapi.errors import UnauthorizedError

from .const import MOCK_DEVICE, MOCK_DEVICE_DATA

# pytest_plugins = "pytest_homeassistant_custom_component"


# This fixture enables loading custom integrations in all tests.
# Remove to enable selective use of this fixture
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations() -> None:
    """This fixture enables loading custom integrations in all tests."""
    return


# This fixture is used to prevent HomeAssistant from attempting to create and dismiss persistent
# notifications. These calls would fail without this fixture since the persistent_notification
# integration is never loaded during a test.
@pytest.fixture(name="skip_notifications", autouse=True)
def skip_notifications_fixture():
    """Skip notification calls."""
    with (
        patch("homeassistant.components.persistent_notification.async_create"),
        patch("homeassistant.components.persistent_notification.async_dismiss"),
    ):
        yield


@pytest.fixture(name="bypass_async_setup_entry")
def bypass_async_setup_entry_fixture():
    """Bypass the setup entry."""
    with patch("homeassistant.components.uhooair.async_setup_entry", return_value=True):
        yield


@pytest.fixture(name="mock_device")
def mock_device_fixture() -> Device:
    """Mock device."""
    device = Device(MOCK_DEVICE)
    device.update_data(MOCK_DEVICE_DATA)
    return device


@pytest.fixture(name="bypass_login")
def bypass_login_fixture():
    """Bypass the login APIs."""
    with patch("homeassistant.components.uhooair.Client.login"):
        yield


@pytest.fixture(name="bypass_setup_devices")
def bypass_setup_devices_fixture():
    """Bypass setting up devices."""
    with patch("homeassistant.components.uhooair.Client.setup_devices"):
        yield


@pytest.fixture(name="error_on_login")
def error_login_fixture():
    """Bypass Login error mock."""
    with patch(
        "homeassistant.components.uhooair.Client.login",
        side_effect=UnauthorizedError,
    ):
        yield


@pytest.fixture(name="bypass_get_latest_data")
def bypass_get_lastest_data_fixture():
    """Bypass get latest data."""
    with patch("homeassistant.components.uhooair.Client.get_latest_data"):
        yield


@pytest.fixture(name="bypass_get_devices")
def bypass_get_devices_fixture(mock_device):
    """Bypass get devices."""
    devices = {mock_device.serial_number: mock_device}
    with patch(
        "homeassistant.components.uhooair.Client.get_devices", return_value=devices
    ):
        yield
