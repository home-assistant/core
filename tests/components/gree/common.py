"""Common helpers for gree test cases."""
import asyncio
import logging
from unittest.mock import AsyncMock, Mock

from greeclimate.discovery import Listener

from homeassistant.components.gree.const import DISCOVERY_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class FakeDiscovery:
    """Mock class replacing Gree device discovery."""

    def __init__(self, timeout: int = DISCOVERY_TIMEOUT) -> None:
        """Initialize the class."""
        self.mock_devices = [build_device_mock()]
        self.timeout = timeout
        self._listeners = []
        self.scan_count = 0

    def add_listener(self, listener: Listener) -> None:
        """Add an event listener."""
        self._listeners.append(listener)

    async def scan(self, wait_for: int = 0):
        """Search for devices, return mocked data."""
        self.scan_count += 1
        _LOGGER.info("CALLED SCAN %d TIMES", self.scan_count)

        infos = [x.device_info for x in self.mock_devices]
        for listener in self._listeners:
            [await listener.device_found(x) for x in infos]

        if wait_for:
            await asyncio.sleep(wait_for)

        return infos


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
        current_temperature=25,
        power=False,
        sleep=False,
        quiet=False,
        turbo=False,
        power_save=False,
        steady_heat=False,
    )
    return mock
