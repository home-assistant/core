"""Pytest module configuration."""

from unittest.mock import AsyncMock, Mock

MOCK_DEVICE = {
    "channels": "[0]",
    "devHardWare": "1.1.2",
    "devSoftWare": "1.1.1",
    "devName": "em06",
    "deviceType": "em06",
    "ip": "192.168.1.1",
    "mac": "test-mac",
    "port": 80,
    "subType": "eu",
    "uuid": "abc",
}


def build_device_mock():
    """Build mock device object."""
    return Mock(
        uuid="abc",
        dev_name="em06",
        device_type="em06",
        fmware_version="1.1.1",
        hdware_version="1.1.2",
        inner_ip="192.168.1.1",
        port="80",
        mac="test-mac",
        sub_type="eu",
        channels=[0],
    )


def mock_switch_device():
    """Build mock  base device object."""
    return Mock(
        device_info=build_device_mock(),
        uuid="abc",
        dev_name="em06",
        device_type="em06",
        fmware_version="1.1.1",
        hdware_version="1.1.2",
        inner_ip="192.168.1.1",
        port="80",
        mac="test-mac",
        sub_type="eu",
        channels=[0],
        async_handle_update=AsyncMock(),
        async_turn_on=AsyncMock(),
        async_turn_off=AsyncMock(),
        async_toggle=AsyncMock(),
    )


def mock_discovery():
    """Mock class replacing meross_can device discovery."""
    mock_discovery = Mock()
    mock_discovery.initialize = AsyncMock()
    mock_discovery.broadcast_msg = AsyncMock(return_value=MOCK_DEVICE)
    mock_discovery.closeDiscovery = Mock()
    return mock_discovery
