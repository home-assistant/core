"""Test helpers for Freebox."""
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import (
    DATA_CALL_GET_CALLS_LOG,
    DATA_CONNECTION_GET_STATUS,
    DATA_HOME_GET_NODES,
    DATA_HOME_GET_VALUES,
    DATA_LAN_GET_HOSTS_LIST,
    DATA_STORAGE_GET_DISKS,
    DATA_STORAGE_GET_RAIDS,
    DATA_SYSTEM_GET_CONFIG,
    WIFI_GET_GLOBAL_CONFIG,
)

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_path():
    """Mock path lib."""
    with patch("homeassistant.components.freebox.router.Path"):
        yield


@pytest.fixture
def mock_device_registry_devices(hass: HomeAssistant, device_registry):
    """Create device registry devices so the device tracker entities are enabled."""
    config_entry = MockConfigEntry(domain="something_else")
    config_entry.add_to_hass(hass)

    for idx, device in enumerate(
        (
            "68:A3:78:00:00:00",
            "8C:97:EA:00:00:00",
            "DE:00:B0:00:00:00",
            "DC:00:B0:00:00:00",
            "5E:65:55:00:00:00",
        )
    ):
        device_registry.async_get_or_create(
            name=f"Device {idx}",
            config_entry_id=config_entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, device)},
        )


@pytest.fixture(name="router")
def mock_router(mock_device_registry_devices):
    """Mock a successful connection."""
    with patch("homeassistant.components.freebox.router.Freepybox") as service_mock:
        instance = service_mock.return_value
        instance.open = AsyncMock()
        instance.system.get_config = AsyncMock(return_value=DATA_SYSTEM_GET_CONFIG)
        # sensor
        instance.call.get_calls_log = AsyncMock(return_value=DATA_CALL_GET_CALLS_LOG)
        instance.storage.get_disks = AsyncMock(return_value=DATA_STORAGE_GET_DISKS)
        instance.storage.get_raids = AsyncMock(return_value=DATA_STORAGE_GET_RAIDS)
        # home devices
        instance.home.get_home_nodes = AsyncMock(return_value=DATA_HOME_GET_NODES)
        instance.home.get_home_endpoint_value = AsyncMock(
            return_value=DATA_HOME_GET_VALUES
        )
        instance.connection.get_status = AsyncMock(
            return_value=DATA_CONNECTION_GET_STATUS
        )
        # switch
        instance.wifi.get_global_config = AsyncMock(return_value=WIFI_GET_GLOBAL_CONFIG)
        # device_tracker
        instance.lan.get_hosts_list = AsyncMock(return_value=DATA_LAN_GET_HOSTS_LIST)
        instance.close = AsyncMock()
        yield service_mock
