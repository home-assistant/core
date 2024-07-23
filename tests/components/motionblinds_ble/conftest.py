"""Setup the Motionblinds Bluetooth tests."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

TEST_MAC = "abcd"
TEST_NAME = f"MOTION_{TEST_MAC.upper()}"
TEST_ADDRESS = "test_adress"


@pytest.fixture(name="motionblinds_ble_connect", autouse=True)
def motion_blinds_connect_fixture(enable_bluetooth):
    """Mock motion blinds ble connection and entry setup."""
    device = Mock()
    device.name = TEST_NAME
    device.address = TEST_ADDRESS

    bleak_scanner = AsyncMock()
    bleak_scanner.discover.return_value = [device]

    with (
        patch(
            "homeassistant.components.motionblinds_ble.config_flow.bluetooth.async_scanner_count",
            return_value=1,
        ),
        patch(
            "homeassistant.components.motionblinds_ble.config_flow.bluetooth.async_get_scanner",
            return_value=bleak_scanner,
        ),
        patch(
            "homeassistant.components.motionblinds_ble.async_setup_entry",
            return_value=True,
        ),
    ):
        yield bleak_scanner, device
