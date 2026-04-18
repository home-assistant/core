"""Tests for the UniFi Discovery integration."""

from collections.abc import Generator
from contextlib import contextmanager
from types import MappingProxyType
from unittest.mock import AsyncMock, MagicMock, patch

from unifi_discovery import AIOUnifiScanner, UnifiDevice, UnifiService

DEVICE_HOSTNAME = "unvr"
DEVICE_IP_ADDRESS = "127.0.0.1"
DEVICE_MAC_ADDRESS = "aa:bb:cc:dd:ee:ff"
DIRECT_CONNECT_DOMAIN = "x.ui.direct"


UNIFI_DISCOVERY_PROTECT = UnifiDevice(
    source_ip=DEVICE_IP_ADDRESS,
    hw_addr=DEVICE_MAC_ADDRESS,
    platform=DEVICE_HOSTNAME,
    hostname=DEVICE_HOSTNAME,
    services={UnifiService.Protect: True},
    direct_connect_domain=DIRECT_CONNECT_DOMAIN,
)

UNIFI_DISCOVERY_NO_MAC = UnifiDevice(
    source_ip=DEVICE_IP_ADDRESS,
    hw_addr=None,
    platform=DEVICE_HOSTNAME,
    hostname=DEVICE_HOSTNAME,
    services={UnifiService.Protect: True},
    direct_connect_domain=DIRECT_CONNECT_DOMAIN,
)

# In production the crash happens because asdict() deep-copies Enum keys in
# the services dict, and on Python 3.14+ deepcopy traverses into
# Enum.__members__ (a mappingproxy) which cannot be pickled.  Whether
# deepcopy(enum) actually fails depends on the specific CPython build, so
# we force the error reliably by using MappingProxyType directly as the
# services value — deepcopy always fails on it.
UNIFI_DISCOVERY_MAPPINGPROXY_SERVICES = UnifiDevice(
    source_ip=DEVICE_IP_ADDRESS,
    hw_addr=DEVICE_MAC_ADDRESS,
    platform=DEVICE_HOSTNAME,
    hostname=DEVICE_HOSTNAME,
    services=MappingProxyType({UnifiService.Protect: True}),
    direct_connect_domain=DIRECT_CONNECT_DOMAIN,
)


def _patch_discovery(
    device: UnifiDevice | None = None, no_device: bool = False
) -> Generator[MagicMock]:
    mock_aio_discovery = MagicMock(spec=AIOUnifiScanner)
    scanner_return = [] if no_device else [device or UNIFI_DISCOVERY_PROTECT]
    mock_aio_discovery.async_scan = AsyncMock(return_value=scanner_return)
    mock_aio_discovery.found_devices = scanner_return

    @contextmanager
    def _patcher():
        with patch(
            "homeassistant.components.unifi_discovery.discovery.AIOUnifiScanner",
            return_value=mock_aio_discovery,
        ):
            yield mock_aio_discovery

    return _patcher()
