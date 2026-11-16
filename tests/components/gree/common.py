"""Common helpers for gree test cases."""

import asyncio
from ipaddress import IPv4Address
import logging
from unittest.mock import AsyncMock, Mock

from greeclimate.discovery import Listener
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.gree.const import DISCOVERY_TIMEOUT, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

_LOGGER = logging.getLogger(__name__)


class FakeDiscovery:
    """Mock class replacing Gree device discovery."""

    def __init__(self, timeout: int = DISCOVERY_TIMEOUT) -> None:
        """Initialize the class."""
        self.mock_devices = [build_device_mock()]
        self.mock_devices_by_address: dict[str, list[Mock]] = {}
        self.last_mock_infos: dict[str, Mock] = {}
        self.timeout = timeout
        self._listeners = []
        self.scan_count = 0

    def add_listener(self, listener: Listener) -> None:
        """Add an event listener."""
        self._listeners.append(listener)

    async def scan(
        self,
        wait_for: int = 0,
        bcast_ifaces: list[IPv4Address] | None = None,
        *,
        target_addresses: list[IPv4Address] | None = None,
    ) -> list[Mock]:
        """Search for devices, return mocked data."""
        self.scan_count += 1
        _LOGGER.info("CALLED SCAN %d TIMES", self.scan_count)

        mock_infos = [x.device_info for x in self.mock_devices]
        mock_infos.extend(
            device.device_info
            for address in target_addresses or bcast_ifaces or []
            for device in self.mock_devices_by_address.get(str(address), [])
        )

        new_infos = []
        updated_infos = []
        for info in mock_infos:
            last_info = self.last_mock_infos.get(info.mac)
            if last_info is None:
                new_infos.append(info)
            elif info.ip != last_info.ip:
                updated_infos.append(info)
            self.last_mock_infos[info.mac] = info
        for listener in self._listeners:
            [await listener.device_found(x) for x in new_infos]
            [await listener.device_update(x) for x in updated_infos]

        if wait_for:
            await asyncio.sleep(wait_for)

        return new_infos


def build_device_info_mock(
    name="fake-device-1", ipAddress="1.1.1.1", mac="aabbcc112233"
):
    """Build mock device info structure."""
    mock = Mock(ip=ipAddress, port=7000, mac=mac)
    mock.name = name
    return mock


def build_device_mock(name="fake-device-1", ipAddress="1.1.1.1", mac="aabbcc112233"):
    """Build a device mock that captures registered response callbacks."""
    mock = Mock(
        device_info=build_device_info_mock(name, ipAddress, mac),
        name=name,
        bind=AsyncMock(),
        update_state=AsyncMock(),
        push_state_update=AsyncMock(),
        raw_properties={},
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
        callbacks={},
    )
    mock.add_handler.side_effect = mock.callbacks.__setitem__
    return mock


async def async_setup_gree(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the gree platform."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    await async_setup_component(hass, DOMAIN, {DOMAIN: {"climate": {}}})
    await hass.async_block_till_done()
    return entry
