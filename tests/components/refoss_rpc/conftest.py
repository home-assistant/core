"""Test configuration for refoss_rpc."""

from unittest.mock import Mock, PropertyMock, patch

from aiorefoss.rpc_device import RpcDevice, RpcUpdateType
import pytest

from homeassistant.components.refoss_rpc.const import EVENT_REFOSS_CLICK
from homeassistant.core import HomeAssistant

from tests.common import async_capture_events

MOCK_CONFIG = {
    "input:1": {"id": 1, "name": "test input", "type": "button"},
    "switch:1": {"id": 1, "name": "test switch"},
    "wifi": {"sta_1": {"enable": True}, "sta_2": {"enable": False}},
}


MOCK_REFOSS_DEVICE = {
    "name": "Test name",
    "mac": "test-mac",
    "model": "r11",
    "dev_id": "refoss-r11-743af4da2f5a",
    "fw_ver": "1",
    "hw_ver": "1",
    "auth_en": False,
}


MOCK_STATUS = {
    "switch:1": {
        "id": 1,
        "output": True,
        "apower": 0,
        "voltage": 0,
        "current": 0,
        "month_consumption": 0,
    },
    "input:1": {"id": 1, "state": False},
    "cloud": {"connected": False},
    "sys": {
        "temperature": {"tc": 22.0},
        "restart_required": False,
        "uptime": 100,
        "available_updates": {"version": "2"},
    },
    "wifi": {"rssi": -30},
}


@pytest.fixture
def events(hass: HomeAssistant):
    """Yield caught refoss_click events."""
    return async_capture_events(hass, EVENT_REFOSS_CLICK)


def _mock_rpc_device():
    """Mock rpc  device."""
    device = Mock(
        spec=RpcDevice,
        config=MOCK_CONFIG,
        event={},
        refoss=MOCK_REFOSS_DEVICE,
        hostname="test-host",
        status=MOCK_STATUS,
        firmware_version="1",
        hw_version="1",
        initialized=True,
        connected=True,
        model="r11",
    )
    type(device).name = PropertyMock(return_value="Test name")
    return device


@pytest.fixture
async def mock_rpc_device():
    """Mock rpc device."""
    with (
        patch("aiorefoss.rpc_device.RpcDevice.create") as rpc_device_mock,
    ):

        def update():
            rpc_device_mock.return_value.subscribe_updates.call_args[0][0](
                {}, RpcUpdateType.STATUS
            )

        def event():
            rpc_device_mock.return_value.subscribe_updates.call_args[0][0](
                {}, RpcUpdateType.EVENT
            )

        def online():
            rpc_device_mock.return_value.subscribe_updates.call_args[0][0](
                {}, RpcUpdateType.ONLINE
            )

        def disconnected():
            rpc_device_mock.return_value.subscribe_updates.call_args[0][0](
                {}, RpcUpdateType.DISCONNECTED
            )

        def initialized():
            rpc_device_mock.return_value.subscribe_updates.call_args[0][0](
                {}, RpcUpdateType.INITIALIZED
            )

        device = _mock_rpc_device()
        rpc_device_mock.return_value = device
        rpc_device_mock.return_value.mock_disconnected = Mock(side_effect=disconnected)
        rpc_device_mock.return_value.mock_update = Mock(side_effect=update)
        rpc_device_mock.return_value.mock_event = Mock(side_effect=event)
        rpc_device_mock.return_value.mock_online = Mock(side_effect=online)
        rpc_device_mock.return_value.mock_initialized = Mock(side_effect=initialized)

        yield rpc_device_mock.return_value
