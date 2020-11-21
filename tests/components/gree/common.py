"""Common helpers for gree test cases."""
import asyncio

from tests.async_mock import AsyncMock, Mock


class MockDiscovery:
    """Mock class replacing Gree device discovery."""

    def __init__(self, mock_devices):
        """Initialize the class."""
        self._mock_devices = mock_devices

    async def search_devices(self, async_callback=None):
        """Search for devices, return mocked data."""
        infos = [x.device_info for x in self._mock_devices]
        tasks = (
            [asyncio.create_task(async_callback(x)) for x in infos]
            if async_callback
            else None
        )
        return infos, tasks


def build_device_info_mock(
    name="fake-device-1", ipAddress="1.1.1.1", mac="aabbcc112233"
):
    """Build mock device info structure."""
    mock = Mock(ip=ipAddress, port=7000, mac=mac)
    mock.name = name
    return mock


def build_device_mock(name="fake-device-1", ipAddress="1.1.1.1", mac="aabbcc112233"):
    """Build mock device object."""
    mock = Mock(
        device_info=build_device_info_mock(name, ipAddress, mac),
        name=name,
        bind=AsyncMock(),
        update_state=AsyncMock(),
        push_state_update=AsyncMock(),
        temperature_units=0,
        mode=0,
        fan_speed=0,
        horizontal_swing=0,
        vertical_swing=0,
        target_temperature=25,
        power=False,
        sleep=False,
        quiet=False,
        turbo=False,
        power_save=False,
        steady_heat=False,
    )
    return mock
