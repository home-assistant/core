"""Fixtures for tests."""

from unittest.mock import AsyncMock, patch

import pytest

from . import async_connect
from .const import CONNECTED_STATIONS, DISCOVERY_INFO, NEIGHBOR_ACCESS_POINTS, PLCNET


@pytest.fixture()
def mock_device():
    """Mock connecting to a devolo home network device."""
    with patch("devolo_plc_api.device.Device.async_connect", async_connect), patch(
        "devolo_plc_api.device.Device.async_disconnect"
    ), patch(
        "devolo_plc_api.device_api.deviceapi.DeviceApi.async_get_wifi_connected_station",
        new=AsyncMock(return_value=CONNECTED_STATIONS),
    ), patch(
        "devolo_plc_api.device_api.deviceapi.DeviceApi.async_get_wifi_neighbor_access_points",
        new=AsyncMock(return_value=NEIGHBOR_ACCESS_POINTS),
    ), patch(
        "devolo_plc_api.plcnet_api.plcnetapi.PlcNetApi.async_get_network_overview",
        new=AsyncMock(return_value=PLCNET),
    ):
        yield


@pytest.fixture(name="info")
def mock_validate_input():
    """Mock setup entry and user input."""
    info = {
        "serial_number": DISCOVERY_INFO.properties["SN"],
        "title": DISCOVERY_INFO.properties["Product"],
    }

    with patch(
        "homeassistant.components.devolo_home_network.config_flow.validate_input",
        return_value=info,
    ):
        yield info


@pytest.fixture(autouse=True)
def devolo_home_network_mock_async_zeroconf(mock_async_zeroconf):
    """Auto mock zeroconf."""
