"""Tests for the bluetooth component."""

from unittest.mock import patch

import pytest


@pytest.fixture(name="operating_system_85")
def mock_operating_system_85():
    """Mock running Home Assistant Operating system 8.5."""
    with patch("homeassistant.components.hassio.is_hassio", return_value=True), patch(
        "homeassistant.components.hassio.get_os_info",
        return_value={
            "version": "8.5",
            "version_latest": "10.0.dev20220912",
            "update_available": False,
            "board": "odroid-n2",
            "boot": "B",
            "data_disk": "/dev/mmcblk1p4",
        },
    ), patch("homeassistant.components.hassio.get_info", return_value={}), patch(
        "homeassistant.components.hassio.get_host_info", return_value={}
    ):
        yield


@pytest.fixture(name="operating_system_90")
def mock_operating_system_90():
    """Mock running Home Assistant Operating system 9.0."""
    with patch("homeassistant.components.hassio.is_hassio", return_value=True), patch(
        "homeassistant.components.hassio.get_os_info",
        return_value={
            "version": "9.0.dev20220912",
            "version_latest": "10.0.dev20220912",
            "update_available": False,
            "board": "odroid-n2",
            "boot": "B",
            "data_disk": "/dev/mmcblk1p4",
        },
    ), patch("homeassistant.components.hassio.get_info", return_value={}), patch(
        "homeassistant.components.hassio.get_host_info", return_value={}
    ):
        yield


@pytest.fixture(name="macos_adapter")
def macos_adapter():
    """Fixture that mocks the macos adapter."""
    with patch("bleak.get_platform_scanner_backend_type"), patch(
        "homeassistant.components.bluetooth.platform.system", return_value="Darwin"
    ), patch(
        "homeassistant.components.bluetooth.scanner.platform.system",
        return_value="Darwin",
    ), patch(
        "bluetooth_adapters.systems.platform.system", return_value="Darwin"
    ):
        yield


@pytest.fixture(name="windows_adapter")
def windows_adapter():
    """Fixture that mocks the windows adapter."""
    with patch(
        "bluetooth_adapters.systems.platform.system",
        return_value="Windows",
    ):
        yield


@pytest.fixture(name="no_adapters")
def no_adapter_fixture():
    """Fixture that mocks no adapters on Linux."""
    with patch(
        "homeassistant.components.bluetooth.platform.system", return_value="Linux"
    ), patch(
        "homeassistant.components.bluetooth.scanner.platform.system",
        return_value="Linux",
    ), patch(
        "bluetooth_adapters.systems.platform.system", return_value="Linux"
    ), patch(
        "bluetooth_adapters.systems.linux.LinuxAdapters.refresh"
    ), patch(
        "bluetooth_adapters.systems.linux.LinuxAdapters.adapters",
        {},
    ):
        yield


@pytest.fixture(name="one_adapter")
def one_adapter_fixture():
    """Fixture that mocks one adapter on Linux."""
    with patch(
        "homeassistant.components.bluetooth.platform.system", return_value="Linux"
    ), patch(
        "homeassistant.components.bluetooth.scanner.platform.system",
        return_value="Linux",
    ), patch(
        "bluetooth_adapters.systems.platform.system", return_value="Linux"
    ), patch(
        "bluetooth_adapters.systems.linux.LinuxAdapters.refresh"
    ), patch(
        "bluetooth_adapters.systems.linux.LinuxAdapters.adapters",
        {
            "hci0": {
                "address": "00:00:00:00:00:01",
                "hw_version": "usb:v1D6Bp0246d053F",
                "passive_scan": True,
                "sw_version": "homeassistant",
                "manufacturer": "ACME",
                "product": "Bluetooth Adapter 5.0",
                "product_id": "aa01",
                "vendor_id": "cc01",
            },
        },
    ):
        yield


@pytest.fixture(name="two_adapters")
def two_adapters_fixture():
    """Fixture that mocks two adapters on Linux."""
    with patch(
        "homeassistant.components.bluetooth.platform.system", return_value="Linux"
    ), patch(
        "homeassistant.components.bluetooth.scanner.platform.system",
        return_value="Linux",
    ), patch(
        "bluetooth_adapters.systems.platform.system", return_value="Linux"
    ), patch(
        "bluetooth_adapters.systems.linux.LinuxAdapters.refresh"
    ), patch(
        "bluetooth_adapters.systems.linux.LinuxAdapters.adapters",
        {
            "hci0": {
                "address": "00:00:00:00:00:01",
                "hw_version": "usb:v1D6Bp0246d053F",
                "passive_scan": False,
                "sw_version": "homeassistant",
                "manufacturer": "ACME",
                "product": "Bluetooth Adapter 5.0",
                "product_id": "aa01",
                "vendor_id": "cc01",
                "connection_slots": 1,
            },
            "hci1": {
                "address": "00:00:00:00:00:02",
                "hw_version": "usb:v1D6Bp0246d053F",
                "passive_scan": True,
                "sw_version": "homeassistant",
                "manufacturer": "ACME",
                "product": "Bluetooth Adapter 5.0",
                "product_id": "aa01",
                "vendor_id": "cc01",
                "connection_slots": 2,
            },
        },
    ):
        yield


@pytest.fixture(name="one_adapter_old_bluez")
def one_adapter_old_bluez():
    """Fixture that mocks two adapters on Linux."""
    with patch(
        "homeassistant.components.bluetooth.platform.system", return_value="Linux"
    ), patch(
        "homeassistant.components.bluetooth.scanner.platform.system",
        return_value="Linux",
    ), patch(
        "bluetooth_adapters.systems.platform.system", return_value="Linux"
    ), patch(
        "bluetooth_adapters.systems.linux.LinuxAdapters.refresh"
    ), patch(
        "bluetooth_adapters.systems.linux.LinuxAdapters.adapters",
        {
            "hci0": {
                "address": "00:00:00:00:00:01",
                "hw_version": "usb:v1D6Bp0246d053F",
                "passive_scan": False,
                "sw_version": "homeassistant",
                "manufacturer": "ACME",
                "product": "Bluetooth Adapter 5.0",
                "product_id": "aa01",
                "vendor_id": "cc01",
            },
        },
    ):
        yield


@pytest.fixture(name="disable_new_discovery_flows")
def disable_new_discovery_flows_fixture():
    """Fixture that disables new discovery flows.

    We want to disable new discovery flows as we are testing the
    BluetoothManager and not the discovery flows. This fixture
    will patch the discovery_flow.async_create_flow method to
    ensure we do not load other integrations.
    """
    with patch(
        "homeassistant.components.bluetooth.manager.discovery_flow.async_create_flow"
    ) as mock_create_flow:
        yield mock_create_flow
