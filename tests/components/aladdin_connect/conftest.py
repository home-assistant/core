"""Fixtures for the Aladdin Connect integration tests."""
from unittest import mock
from unittest.mock import AsyncMock

import pytest

DEVICE_CONFIG_OPEN = {
    "device_id": 533255,
    "door_number": 1,
    "name": "home",
    "status": "open",
    "link_status": "Connected",
    "serial": "12345",
    "model": "02",
    "rssi": -67,
    "ble_strength": 0,
    "vendor": "GENIE",
    "battery_level": 0,
}


@pytest.fixture(name="mock_aladdinconnect_api")
def fixture_mock_aladdinconnect_api():
    """Set up aladdin connect API fixture."""
    with mock.patch(
        "homeassistant.components.aladdin_connect.AladdinConnectClient"
    ) as mock_opener:
        mock_opener.login = AsyncMock(return_value=True)
        mock_opener.close = AsyncMock(return_value=True)

        mock_opener.async_get_door_status = AsyncMock(return_value="open")
        mock_opener.get_door_status.return_value = "open"
        mock_opener.async_get_door_link_status = AsyncMock(return_value="connected")
        mock_opener.get_door_link_status.return_value = "connected"
        mock_opener.async_get_battery_status = AsyncMock(return_value="99")
        mock_opener.get_battery_status.return_value = "99"
        mock_opener.async_get_rssi_status = AsyncMock(return_value="-55")
        mock_opener.get_rssi_status.return_value = "-55"
        mock_opener.async_get_ble_strength = AsyncMock(return_value="-45")
        mock_opener.get_ble_strength.return_value = "-45"
        mock_opener.get_doors = AsyncMock(return_value=[DEVICE_CONFIG_OPEN])
        mock_opener.doors = [DEVICE_CONFIG_OPEN]
        mock_opener.register_callback = mock.Mock(return_value=True)
        mock_opener.open_door = AsyncMock(return_value=True)
        mock_opener.close_door = AsyncMock(return_value=True)

    return mock_opener
