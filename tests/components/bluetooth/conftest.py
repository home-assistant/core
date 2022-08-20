"""Tests for the bluetooth component."""

from unittest.mock import patch

import pytest


@pytest.fixture(name="macos_adapter")
def macos_adapter():
    """Fixture that mocks the macos adapter."""
    with patch(
        "homeassistant.components.bluetooth.util.platform.system", return_value="Darwin"
    ):
        yield


@pytest.fixture(name="windows_adapter")
def windows_adapter():
    """Fixture that mocks the windows adapter."""
    with patch(
        "homeassistant.components.bluetooth.util.platform.system",
        return_value="Windows",
    ):
        yield


@pytest.fixture(name="one_adapter")
def one_adapter_fixture():
    """Fixture that mocks one adapter on Linux."""
    with patch(
        "homeassistant.components.bluetooth.util.platform.system", return_value="Linux"
    ), patch(
        "bluetooth_adapters.get_bluetooth_adapter_details",
        return_value={
            "hci0": {
                "org.bluez.Adapter1": {
                    "Address": "00:00:00:00:00:01",
                    "Name": "BlueZ 4.63",
                    "Modalias": "usbid:1234",
                }
            },
        },
    ):
        yield


@pytest.fixture(name="two_adapters")
def two_adapters_fixture():
    """Fixture that mocks two adapters on Linux."""
    with patch(
        "homeassistant.components.bluetooth.util.platform.system", return_value="Linux"
    ), patch(
        "bluetooth_adapters.get_bluetooth_adapter_details",
        return_value={
            "hci0": {
                "org.bluez.Adapter1": {
                    "Address": "00:00:00:00:00:01",
                    "Name": "BlueZ 4.63",
                    "Modalias": "usbid:1234",
                }
            },
            "hci1": {
                "org.bluez.Adapter1": {
                    "Address": "00:00:00:00:00:02",
                    "Name": "BlueZ 4.63",
                    "Modalias": "usbid:1234",
                }
            },
        },
    ):
        yield
