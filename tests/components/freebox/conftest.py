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
        instance = service_mock.return_value
        instance.open = AsyncMock()
        instance.system.get_config = AsyncMock(return_value=DATA_SYSTEM_GET_CONFIG)
        # sensor
        instance.call.get_calls_log = AsyncMock(return_value=DATA_CALL_GET_CALLS_LOG)
        instance.storage.get_disks = AsyncMock(return_value=DATA_STORAGE_GET_DISKS)
        instance.connection.get_status = AsyncMock(
            return_value=DATA_CONNECTION_GET_STATUS
        )
        # switch
        instance.wifi.get_global_config = AsyncMock(return_value=WIFI_GET_GLOBAL_CONFIG)
        # device_tracker
        instance.lan.get_hosts_list = AsyncMock(return_value=DATA_LAN_GET_HOSTS_LIST)
        instance.close = AsyncMock()
        yield service_mock
