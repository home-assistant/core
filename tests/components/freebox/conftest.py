"""Test helpers for Freebox."""
from unittest.mock import AsyncMock, patch

import pytest

from .const import (
    DATA_CALL_GET_CALLS_LOG,
    DATA_CONNECTION_GET_STATUS,
    DATA_LAN_GET_HOSTS_LIST,
    DATA_STORAGE_GET_DISKS,
    DATA_SYSTEM_GET_CONFIG,
    WIFI_GET_GLOBAL_CONFIG,
)


@pytest.fixture(autouse=True)
def mock_path():
    """Mock path lib."""
    with patch("homeassistant.components.freebox.router.Path"):
        yield


@pytest.fixture(name="router")
def mock_router():
    """Mock a successful connection."""
    with patch("homeassistant.components.freebox.router.Freepybox") as service_mock:
        service_mock.return_value.open = AsyncMock()
        service_mock.return_value.system.get_config = AsyncMock(
            return_value=DATA_SYSTEM_GET_CONFIG
        )
        # sensor
        service_mock.return_value.call.get_calls_log = AsyncMock(
            return_value=DATA_CALL_GET_CALLS_LOG
        )
        service_mock.return_value.storage.get_disks = AsyncMock(
            return_value=DATA_STORAGE_GET_DISKS
        )
        service_mock.return_value.connection.get_status = AsyncMock(
            return_value=DATA_CONNECTION_GET_STATUS
        )
        # switch
        service_mock.return_value.wifi.get_global_config = AsyncMock(
            return_value=WIFI_GET_GLOBAL_CONFIG
        )
        # device_tracker
        service_mock.return_value.lan.get_hosts_list = AsyncMock(
            return_value=DATA_LAN_GET_HOSTS_LIST
        )
        service_mock.return_value.close = AsyncMock()
        yield service_mock
