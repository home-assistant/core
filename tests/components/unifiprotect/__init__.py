"""Tests for the UniFi Protect integration."""

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from uiprotect.data.base import ProtectModel
from unifi_discovery import AIOUnifiScanner, UnifiDevice, UnifiService

DEVICE_HOSTNAME = "unvr"
DEVICE_IP_ADDRESS = "127.0.0.1"
DEVICE_MAC_ADDRESS = "aa:bb:cc:dd:ee:ff"
DIRECT_CONNECT_DOMAIN = "x.ui.direct"


UNIFI_DISCOVERY = UnifiDevice(
    source_ip=DEVICE_IP_ADDRESS,
    hw_addr=DEVICE_MAC_ADDRESS,
    platform=DEVICE_HOSTNAME,
    hostname=DEVICE_HOSTNAME,
    services={UnifiService.Protect: True},
    direct_connect_domain=DIRECT_CONNECT_DOMAIN,
)


UNIFI_DISCOVERY_PARTIAL = UnifiDevice(
    source_ip=DEVICE_IP_ADDRESS,
    hw_addr=DEVICE_MAC_ADDRESS,
    services={UnifiService.Protect: True},
)

pytest.register_assert_rewrite("tests.components.unifiprotect.utils")


def _patch_discovery(device=None, no_device=False):
    mock_aio_discovery = MagicMock(auto_spec=AIOUnifiScanner)
    scanner_return = [] if no_device else [device or UNIFI_DISCOVERY]
    mock_aio_discovery.async_scan = AsyncMock(return_value=scanner_return)
    mock_aio_discovery.found_devices = scanner_return

    @contextmanager
    def _patcher():
        with patch(
            "homeassistant.components.unifiprotect.discovery.AIOUnifiScanner",
            return_value=mock_aio_discovery,
        ):
            yield

    return _patcher()


@contextmanager
def patch_ufp_method(
    obj: ProtectModel, method: str, *args: Any, **kwargs: Any
) -> Generator[MagicMock]:
    """Patch a method on a UniFi Protect pydantic model.

    Pydantic models have frozen fields that cannot be directly patched.
    This context manager temporarily modifies the field descriptor to allow
    patching.

    Note: The field modification is intentionally not restored, as test fixtures
    create fresh model instances for each test.

    Usage:
        with patch_ufp_method(doorbell, "set_lcd_text", new_callable=AsyncMock) as mock:
            await hass.services.async_call(...)
            mock.assert_called_once_with(...)
    """
    obj.__pydantic_fields__[method] = Mock(final=False, frozen=False)
    with patch.object(obj, method, *args, **kwargs) as mock_method:
        yield mock_method
