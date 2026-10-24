"""Common helpers for gree test cases."""

from collections.abc import Callable
from ipaddress import IPv4Address
from unittest.mock import AsyncMock, Mock

from greeclimate.deviceinfo import DeviceInfo
from greeclimate.network import Response
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.gree.const import DISCOVERY_TIMEOUT, DOMAIN
from homeassistant.components.gree.discovery import (
    device_info_to_data,
    normalize_identifier,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


class FakeDiscovery:
    """Return the configured responders for one bounded discovery scan."""

    def __init__(
        self,
        timeout: int = DISCOVERY_TIMEOUT,
        *,
        mock_devices: list[Mock] | None = None,
    ) -> None:
        """Initialize an independent scanner without a lifetime discovery cache."""
        self.timeout = timeout
        self.mock_devices = (
            mock_devices if mock_devices is not None else [build_device_mock()]
        )
        self.closed = False
        self.scan = AsyncMock(side_effect=self._async_scan)
        self.close = Mock(side_effect=self._close)

    async def _async_scan(
        self,
        wait_for: int = 0,
        *,
        target_addresses: list[IPv4Address] | None = None,
    ) -> list[DeviceInfo]:
        """Return fresh responses; destinations and wait are recorded by the mock."""
        if self.closed or target_addresses == []:
            return []
        return [device.device_info for device in self.mock_devices]

    def _close(self) -> None:
        """Retire this scanner idempotently."""
        self.closed = True


def build_device_info_mock(
    name: str = "fake-device-1",
    ipAddress: str = "1.1.1.1",
    identifier: str = "aabbcc112233",
    *,
    port: int = 7000,
    brand: str | None = None,
    model: str | None = None,
    version: str | None = None,
    mid: str | None = None,
) -> DeviceInfo:
    """Build the library's real device information value."""
    return DeviceInfo(ipAddress, port, identifier, name, brand, model, version, mid)


def build_device_mock(
    name: str = "fake-device-1",
    ipAddress: str = "1.1.1.1",
    identifier: str = "aabbcc112233",
    *,
    port: int = 7000,
) -> Mock:
    """Build a device with public state properties and response callbacks."""
    handlers: dict[Response, Callable[..., None]] = {}
    device = Mock(
        device_info=build_device_info_mock(name, ipAddress, identifier, port=port),
        name=name,
        bind=AsyncMock(),
        push_state_update=AsyncMock(),
        raw_properties=Mock(name="raw_properties", spec=dict),
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
        light=True,
        fresh_air=True,
        xfan=True,
        anion=True,
        closed=False,
        handlers=handlers,
    )

    def add_handler(response: Response, handler: Callable[..., None]) -> None:
        handlers[response] = handler

    def emit_response(response: Response) -> None:
        if handler := handlers.get(response):
            handler()

    def close() -> None:
        device.closed = True

    device.add_handler = Mock(side_effect=add_handler)
    device.emit_response = Mock(side_effect=emit_response)
    device.update_state = AsyncMock()
    device.close = Mock(side_effect=close)
    return device


async def async_setup_gree(
    hass: HomeAssistant, mock_device: Mock | None = None
) -> MockConfigEntry:
    """Set up one explicitly enrolled device."""
    info = (mock_device or build_device_mock()).device_info
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        minor_version=1,
        unique_id=normalize_identifier(info.mac),
        title=info.name,
        data=device_info_to_data(info),
    )
    await async_setup_component(hass, DOMAIN, {})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
