"""The Thread integration."""
from __future__ import annotations

from collections.abc import Callable
import dataclasses
import logging

from zeroconf import ServiceListener, Zeroconf
from zeroconf.asyncio import AsyncZeroconf

from homeassistant.components import zeroconf
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

KNOWN_BRANDS: dict[str | None, str] = {
    "Apple Inc.": "apple",
    "Google Inc.": "google",
    "HomeAssistant": "homeassistant",
}
THREAD_TYPE = "_meshcop._udp.local."


@dataclasses.dataclass
class ThreadRouterDiscoveryData:
    """Thread router discovery data."""

    brand: str | None
    network_name: str | None
    product_name: str | None
    vendor_name: str | None


class ThreadRouterDiscovery:
    """mDNS based Thread router discovery."""

    class ThreadServiceListener(ServiceListener):
        """Service listener which listens for thread routers."""

        def __init__(
            self,
            hass: HomeAssistant,
            aiozc: AsyncZeroconf,
            router_discovered: Callable,
            router_removed: Callable,
        ) -> None:
            """Initialize."""
            self._aiozc = aiozc
            self._hass = hass
            self._router_discovered = router_discovered
            self._router_removed = router_removed

        def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
            """Handle service added."""
            _LOGGER.debug("add_service %s", name)
            self._hass.async_create_task(self._add_update_service(type_, name))

        def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
            """Handle service removed."""
            _LOGGER.debug("remove_service %s", name)
            self._router_removed(name)

        def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
            """Handle service updated."""
            _LOGGER.debug("update_service %s", name)
            self._hass.async_create_task(self._add_update_service(type_, name))

        async def _add_update_service(self, type_: str, name: str):
            """Add or update a service."""
            service = None
            tries = 0
            while service is None and tries < 4:
                service = await self._aiozc.async_get_service_info(type_, name)
                tries += 1

            if not service:
                _LOGGER.debug("_add_update_service failed to add %s, %s", type_, name)
                return

            def try_decode(value: bytes | None) -> str | None:
                """Try decoding UTF-8."""
                if value is None:
                    return None
                try:
                    return value.decode()
                except UnicodeDecodeError:
                    return None

            _LOGGER.debug("_add_update_service %s %s", name, service)
            network_name = try_decode(service.properties.get(b"nn"))
            product_name = try_decode(service.properties.get(b"pn"))
            vendor_name = try_decode(service.properties.get(b"vn"))
            data = ThreadRouterDiscoveryData(
                brand=KNOWN_BRANDS.get(vendor_name),
                network_name=network_name,
                product_name=product_name,
                vendor_name=vendor_name,
            )
            self._router_discovered(name, data)

    def __init__(
        self,
        hass: HomeAssistant,
        router_discovered: Callable[[str, ThreadRouterDiscoveryData], None],
        router_removed: Callable[[str], None],
    ) -> None:
        """Initialize."""
        self._hass = hass
        self._aiozc: AsyncZeroconf | None = None
        self._router_discovered = router_discovered
        self._router_removed = router_removed
        self._service_listener: ThreadRouterDiscovery.ThreadServiceListener | None = (
            None
        )

    async def async_start(self) -> None:
        """Start discovery."""
        self._aiozc = aiozc = await zeroconf.async_get_async_instance(self._hass)
        self._service_listener = self.ThreadServiceListener(
            self._hass, aiozc, self._router_discovered, self._router_removed
        )
        await aiozc.async_add_service_listener(THREAD_TYPE, self._service_listener)

    async def async_stop(self) -> None:
        """Stop discovery."""
        if not self._aiozc or not self._service_listener:
            return
        await self._aiozc.async_remove_service_listener(self._service_listener)
        self._service_listener = None
