"""Scanner for apple_tv that uses HomeAssistant zeroconf."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
import contextlib
from ipaddress import IPv4Address, ip_address
from typing import cast

from pyatv import interface
from pyatv.const import Protocol
from pyatv.core import mdns
from pyatv.core.scan import BaseScanner
from pyatv.protocols import PROTOCOLS
from zeroconf import DNSPointer, DNSQuestionType
from zeroconf.asyncio import AsyncServiceInfo, AsyncZeroconf

from homeassistant.components.zeroconf import async_get_async_instance
from homeassistant.core import HomeAssistant

DEVICE_INFO_TYPE = "_device-info._tcp.local."
NAME_USED_FOR_DEVICE_INFO = {"_airplay._tcp.local.", "_raop._tcp.local."}


def _service_short_name(info: AsyncServiceInfo) -> str:
    return info.name[: -(len(info.type) + 1)]


def _device_info_name(info: AsyncServiceInfo) -> str | None:
    if info.type not in NAME_USED_FOR_DEVICE_INFO:
        return None
    short_name = _service_short_name(info)
    if "@" in short_name:
        return short_name.split("@")[1]
    return short_name


def _first_non_link_local_or_v6_address(addresses: list[bytes]) -> str | None:
    """Return the first ipv6 or non-link local ipv4 address."""
    for address in addresses:
        ip_addr = ip_address(address)
        if not ip_addr.is_link_local or ip_addr.version == 6:
            return str(ip_addr)
    return None


class HassZeroconfScanner(BaseScanner):
    """Service discovery using zeroconf."""

    def __init__(
        self,
        zc: AsyncZeroconf,
        hosts: list[IPv4Address] | None = None,
        identifier: str | set[str] | None = None,
    ) -> None:
        """Initialize a new scanner."""
        super().__init__()
        self.zc = zc
        self.hosts: set[str] = {str(host) for host in hosts} if hosts else set()
        self.identifiers: set[str] = (
            identifier if isinstance(identifier, set) else set()
        )
        self.loop = asyncio.get_running_loop()

    async def _async_services_by_addresses(
        self, timeout: int
    ) -> dict[str, list[AsyncServiceInfo]]:
        infos: list[AsyncServiceInfo] = []
        zc_timeout = timeout * 1000
        zeroconf = self.zc.zeroconf
        zc_types = [f"{service}." for service in self._services]
        # Note this only works if a ServiceBrowser is already
        # running for the given type (since its in the manifest this is ok)
        infos = [
            AsyncServiceInfo(zc_type, cast(DNSPointer, record).alias)
            for zc_type in zc_types
            for record in zeroconf.cache.entries_with_name(zc_type)
        ]
        await asyncio.gather(
            *[info.async_request(zeroconf, zc_timeout) for info in infos]
        )
        services_by_address: dict[str, list[AsyncServiceInfo]] = {}
        for info in infos:
            if address := _first_non_link_local_or_v6_address(info.addresses):
                services_by_address.setdefault(address, []).append(info)

        return services_by_address

    async def _async_models_by_name(
        self, names: Iterable[str], timeout: int
    ) -> dict[str, str]:
        zc_timeout = timeout * 1000
        zeroconf = self.zc.zeroconf
        name_to_model: dict[str, str] = {}
        device_infos = {
            name: AsyncServiceInfo(DEVICE_INFO_TYPE, f"{name}.{DEVICE_INFO_TYPE}")
            for name in names
        }
        await asyncio.gather(
            *[
                info.async_request(
                    zeroconf, zc_timeout, question_type=DNSQuestionType.QU
                )
                for info in device_infos.values()
            ]
        )
        for name, info in device_infos.items():
            if possible_model := info.properties.get(b"model"):
                with contextlib.suppress(UnicodeDecodeError):
                    name_to_model[name] = possible_model.decode("utf-8")
        return name_to_model

    async def process(self, timeout: int) -> None:
        """Start to process devices and services."""
        services_by_address = await self._async_services_by_addresses(timeout)
        name_by_address: dict[str, str] = {}
        responses_by_address: dict[str, mdns.Response] = {}
        for address, services in services_by_address.items():
            if self.hosts and address not in self.hosts:
                continue
            atv_services = []
            for service in services:
                atv_type = service.type[:-1]
                name = _service_short_name(service)
                if address not in name_by_address:
                    name_by_address[address] = name
                try:
                    decoded_properties = {
                        k.decode("ascii"): v.decode("utf-8")
                        for k, v in service.properties.items()
                    }
                except UnicodeDecodeError:
                    continue
                atv_services.append(
                    mdns.Service(
                        atv_type, name, address, service.port, decoded_properties
                    )
                )
            responses_by_address[address] = mdns.Response(
                services=atv_services,
                deep_sleep=all(service.port == 0 for service in services),
                model=None,
            )
        if not responses_by_address:
            return
        name_to_model = await self._async_models_by_name(
            name_by_address.values(), timeout
        )
        import pprint

        for address, response in responses_by_address.items():
            if (name_for_address := name_by_address.get(address)) is not None:
                if model := name_to_model.get(name_for_address):
                    response.model = model
            pprint.pprint(response)
            self.handle_response(response)


async def scan(
    hass: HomeAssistant,
    timeout: int = 5,
    identifier: str | set[str] | None = None,
    protocol: Protocol | set[Protocol] | None = None,
    hosts: list[str] = None,
) -> list[interface.BaseConfig]:
    """Scan for Apple TVs on network and return their configurations."""

    def _should_include(atv):
        if not atv.ready:
            return False

        if identifier:
            target = identifier if isinstance(identifier, set) else {identifier}
            return not target.isdisjoint(atv.all_identifiers)

        return True

    async_zc = await async_get_async_instance(hass)
    if hosts:
        scanner = HassZeroconfScanner(
            zc=async_zc, hosts=[IPv4Address(host) for host in hosts]
        )
    else:
        scanner = HassZeroconfScanner(zc=async_zc, identifier=identifier)

    protocols = set()
    if protocol:
        protocols.update(protocol if isinstance(protocol, set) else {protocol})

    for proto, proto_methods in PROTOCOLS.items():
        # If specific protocols was given, skip this one if it isn't listed
        if protocol and proto not in protocols:
            continue

        scanner.add_service_info(proto, proto_methods.service_info)

        for service_type, handler in proto_methods.scan().items():
            scanner.add_service(
                service_type,
                handler,
                proto_methods.device_info,
            )

    devices = (await scanner.discover(timeout)).values()
    return [device for device in devices if _should_include(device)]
