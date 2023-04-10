"""The Thread integration."""
from __future__ import annotations

from collections.abc import Callable
import dataclasses
import logging
from typing import cast

from zeroconf import BadTypeInNameException, DNSPointer, ServiceListener, Zeroconf
from zeroconf.asyncio import AsyncServiceInfo, AsyncZeroconf

from homeassistant.components import zeroconf
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

KNOWN_BRANDS: dict[str | None, str] = {
    "Apple Inc.": "apple",
    "Google Inc.": "google",
    "HomeAssistant": "homeassistant",
    "Home Assistant": "homeassistant",
}
THREAD_TYPE = "_meshcop._udp.local."
CLASS_IN = 1
TYPE_PTR = 12


@dataclasses.dataclass
class ThreadRouterDiscoveryData:
    """Thread router discovery data."""

    brand: str | None
    extended_pan_id: str | None
    model_name: str | None
    network_name: str | None
    server: str | None
    vendor_name: str | None
    addresses: list[str] | None
    thread_version: str | None


def async_discovery_data_from_service(
    service: AsyncServiceInfo,
) -> ThreadRouterDiscoveryData:
    """Get a ThreadRouterDiscoveryData from an AsyncServiceInfo."""

    def try_decode(value: bytes | None) -> str | None:
        """Try decoding UTF-8."""
        if value is None:
            return None
        try:
            return value.decode()
        except UnicodeDecodeError:
            return None

    ext_pan_id = service.properties.get(b"xp")
    network_name = try_decode(service.properties.get(b"nn"))
    model_name = try_decode(service.properties.get(b"mn"))
    server = service.server
    vendor_name = try_decode(service.properties.get(b"vn"))
    thread_version = try_decode(service.properties.get(b"tv"))
    return ThreadRouterDiscoveryData(
        brand=KNOWN_BRANDS.get(vendor_name),
        extended_pan_id=ext_pan_id.hex() if ext_pan_id is not None else None,
        model_name=model_name,
        network_name=network_name,
        server=server,
        vendor_name=vendor_name,
        addresses=service.parsed_addresses(),
        thread_version=thread_version,
    )


def async_read_zeroconf_cache(aiozc: AsyncZeroconf) -> list[ThreadRouterDiscoveryData]:
    """Return all meshcop records already in the zeroconf cache."""
    results = []

    records = aiozc.zeroconf.cache.async_all_by_details(THREAD_TYPE, TYPE_PTR, CLASS_IN)
    for record in records:
        record = cast(DNSPointer, record)

        try:
            info = AsyncServiceInfo(THREAD_TYPE, record.alias)
        except BadTypeInNameException as ex:
            _LOGGER.debug(
                "Ignoring record with bad type in name: %s: %s", record.alias, ex
            )
            continue

        if not info.load_from_cache(aiozc.zeroconf):
            # data is not fully in the cache, so ignore for now
            continue

        results.append(async_discovery_data_from_service(info))

    return results


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
            self._known_routers: dict[str, tuple[str, ThreadRouterDiscoveryData]] = {}
            self._router_discovered = router_discovered
            self._router_removed = router_removed

        def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
            """Handle service added."""
            _LOGGER.debug("add_service %s", name)
            self._hass.async_create_task(self._add_update_service(type_, name))

        def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
            """Handle service removed."""
            _LOGGER.debug("remove_service %s", name)
            if name not in self._known_routers:
                return
            extended_mac_address, _ = self._known_routers.pop(name)
            self._router_removed(extended_mac_address)

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

            _LOGGER.debug("_add_update_service %s %s", name, service)
            # We use the extended mac address as key, bail out if it's missing
            try:
                extended_mac_address = service.properties[b"xa"].hex()
            except (KeyError, UnicodeDecodeError) as err:
                _LOGGER.debug("_add_update_service failed to parse service %s", err)
                return

            data = async_discovery_data_from_service(service)
            if name in self._known_routers and self._known_routers[name] == (
                extended_mac_address,
                data,
            ):
                _LOGGER.debug(
                    "_add_update_service suppressing identical update for %s", name
                )
                return
            self._known_routers[name] = (extended_mac_address, data)
            self._router_discovered(extended_mac_address, data)

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
