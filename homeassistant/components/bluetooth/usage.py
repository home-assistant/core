"""bluetooth usage utility to handle multiple instances."""

from __future__ import annotations

import bleak
from bleak.backends.service import BleakGATTServiceCollection
import bleak_retry_connector

from .wrappers import HaBleakClientWrapper, HaBleakScannerWrapper

ORIGINAL_BLEAK_SCANNER = bleak.BleakScanner
ORIGINAL_BLEAK_CLIENT = bleak.BleakClient
ORIGINAL_BLEAK_RETRY_CONNECTOR_CLIENT_WITH_SERVICE_CACHE = (
    bleak_retry_connector.BleakClientWithServiceCache
)
ORIGINAL_BLEAK_RETRY_CONNECTOR_CLIENT = bleak_retry_connector.BleakClient


def install_multiple_bleak_catcher() -> None:
    """Wrap the bleak classes to return the shared instance.

    In case multiple instances are detected.
    """
    bleak.BleakScanner = HaBleakScannerWrapper  # type: ignore[misc, assignment]
    bleak.BleakClient = HaBleakClientWrapper  # type: ignore[misc]
    bleak_retry_connector.BleakClientWithServiceCache = HaBleakClientWithServiceCache  # type: ignore[misc,assignment] # noqa: E501
    bleak_retry_connector.BleakClient = HaBleakClientWrapper  # type: ignore[misc] # noqa: E501


def uninstall_multiple_bleak_catcher() -> None:
    """Unwrap the bleak classes."""
    bleak.BleakScanner = ORIGINAL_BLEAK_SCANNER  # type: ignore[misc]
    bleak.BleakClient = ORIGINAL_BLEAK_CLIENT  # type: ignore[misc]
    bleak_retry_connector.BleakClientWithServiceCache = (  # type: ignore[misc]
        ORIGINAL_BLEAK_RETRY_CONNECTOR_CLIENT_WITH_SERVICE_CACHE
    )
    bleak_retry_connector.BleakClient = (  # type: ignore[misc]
        ORIGINAL_BLEAK_RETRY_CONNECTOR_CLIENT
    )


class HaBleakClientWithServiceCache(HaBleakClientWrapper):
    """A BleakClient that implements service caching."""

    def set_cached_services(self, services: BleakGATTServiceCollection | None) -> None:
        """Set the cached services.

        No longer used since bleak 0.17+ has service caching built-in.

        This was only kept for backwards compatibility.
        """
