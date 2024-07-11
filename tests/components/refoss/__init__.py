"""Common helpers for refoss test cases."""

import asyncio
import logging
from unittest.mock import AsyncMock, Mock

from refoss_ha.discovery import Listener

from homeassistant.components.refoss.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


class FakeDiscovery:
    """Mock class replacing refoss device discovery."""

    def __init__(self) -> None:
        """Initialize the class."""
        self.mock_devices = {"abc": build_device_mock()}
        self.last_mock_infos = {}
        self._listeners = []
        self.sock = None

    def add_listener(self, listener: Listener) -> None:
        """Add an event listener."""
        self._listeners.append(listener)

    async def initialize(self) -> None:
        """Initialize socket server."""
        self.sock = Mock()

    async def broadcast_msg(self, wait_for: int = 0):
        """Search for devices, return mocked data."""

        mock_infos = self.mock_devices
        last_mock_infos = self.last_mock_infos

        new_infos = []
        updated_infos = []

        for info in mock_infos.values():
            uuid = info.uuid
            if uuid not in last_mock_infos:
                new_infos.append(info)
            else:
                last_info = self.last_mock_infos[uuid]
                if info.inner_ip != last_info.inner_ip:
                    updated_infos.append(info)

        self.last_mock_infos = mock_infos
        for listener in self._listeners:
            [await listener.device_found(x) for x in new_infos]
            [await listener.device_update(x) for x in updated_infos]

        if wait_for:
            await asyncio.sleep(wait_for)

        return new_infos


def build_device_mock(name="r10", ip="1.1.1.1", mac="aabbcc112233"):
    """Build mock device object."""
    return Mock(
        uuid="abc",
        dev_name=name,
        device_type="r10",
        fmware_version="1.1.1",
        hdware_version="1.1.2",
        inner_ip=ip,
        port="80",
        mac=mac,
        sub_type="eu",
        channels=[0],
    )


def build_base_device_mock(name="r10", ip="1.1.1.1", mac="aabbcc112233"):
    """Build mock  base device object."""
    mock = Mock(
        device_info=build_device_mock(name=name, ip=ip, mac=mac),
        uuid="abc",
        dev_name=name,
        device_type="r10",
        fmware_version="1.1.1",
        hdware_version="1.1.2",
        inner_ip=ip,
        port="80",
        mac=mac,
        sub_type="eu",
        channels=[0],
        async_handle_update=AsyncMock(),
        async_turn_on=AsyncMock(),
        async_turn_off=AsyncMock(),
        async_toggle=AsyncMock(),
    )
    mock.status = {0: True}
    return mock


async def async_setup_refoss(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the refoss platform."""
    entry = MockConfigEntry(domain=DOMAIN)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
