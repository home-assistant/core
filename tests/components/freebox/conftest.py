"""Test helpers for Freebox."""

import json
from unittest.mock import AsyncMock, patch

from freebox_api.exceptions import HttpRequestError
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import (
    DATA_CALL_GET_CALLS_LOG,
    DATA_CONNECTION_GET_STATUS,
    DATA_HOME_GET_NODES,
    DATA_HOME_PIR_GET_VALUE,
    DATA_HOME_SET_VALUE,
    DATA_LAN_GET_HOSTS_LIST,
    DATA_LAN_GET_HOSTS_LIST_GUEST,
    DATA_LAN_GET_HOSTS_LIST_MODE_BRIDGE,
    DATA_LAN_GET_INTERFACES,
    DATA_STORAGE_GET_DISKS,
    DATA_STORAGE_GET_RAIDS,
    DATA_SYSTEM_GET_CONFIG,
    DATA_WIFI_GET_GLOBAL_CONFIG,
)

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_path():
    """Mock path lib."""
    with (
        patch("homeassistant.components.freebox.router.Path"),
        patch("homeassistant.components.freebox.router.os.makedirs"),
    ):
        yield


@pytest.fixture
def mock_device_registry_devices(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
):
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
        # device_tracker
        instance.lan.get_interfaces = AsyncMock(return_value=DATA_LAN_GET_INTERFACES)
        instance.lan.get_hosts_list = AsyncMock(
            side_effect=lambda interface: DATA_LAN_GET_HOSTS_LIST
            if interface == "pub"
            else DATA_LAN_GET_HOSTS_LIST_GUEST
        )
        # sensor
        instance.call.get_calls_log = AsyncMock(return_value=DATA_CALL_GET_CALLS_LOG)
        instance.storage.get_disks = AsyncMock(return_value=DATA_STORAGE_GET_DISKS)
        instance.storage.get_raids = AsyncMock(return_value=DATA_STORAGE_GET_RAIDS)
        instance.connection.get_status = AsyncMock(
            return_value=DATA_CONNECTION_GET_STATUS
        )
        # switch
        instance.wifi.get_global_config = AsyncMock(
            return_value=DATA_WIFI_GET_GLOBAL_CONFIG
        )
        # home devices
        instance.home.get_home_nodes = AsyncMock(return_value=DATA_HOME_GET_NODES)
        instance.home.get_home_endpoint_value = AsyncMock(
            return_value=DATA_HOME_PIR_GET_VALUE
        )
        instance.home.set_home_endpoint_value = AsyncMock(
            return_value=DATA_HOME_SET_VALUE
        )
        instance.close = AsyncMock()
        yield service_mock


@pytest.fixture(name="router_bridge_mode")
def mock_router_bridge_mode(mock_device_registry_devices, router):
    """Mock a successful connection to Freebox Bridge mode."""

    router().lan.get_interfaces = AsyncMock(
        side_effect=HttpRequestError(
            f"Request failed (APIResponse: {json.dumps(DATA_LAN_GET_HOSTS_LIST_MODE_BRIDGE)})"
        )
    )

    router().lan.get_hosts_list = AsyncMock(
        side_effect=HttpRequestError(
            f"Request failed (APIResponse: {json.dumps(DATA_LAN_GET_HOSTS_LIST_MODE_BRIDGE)})"
        )
    )

    return router


@pytest.fixture
def mock_router_bridge_mode_error(mock_device_registry_devices, router):
    """Mock a failed connection to Freebox Bridge mode."""

    router().lan.get_hosts_list = AsyncMock(
        side_effect=HttpRequestError("Request failed (APIResponse: some unknown error)")
    )

    return router
