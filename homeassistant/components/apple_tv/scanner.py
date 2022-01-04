"""Scanner for apple_tv that uses HomeAssistant zeroconf."""
from __future__ import annotations

import asyncio
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

from homeassistant.components.zeroconf import DEVICE_INFO_TYPE, async_get_async_instance
from homeassistant.core import HomeAssistant

NAME_USED_FOR_DEVICE_INFO = {"_airplay._tcp.local.", "_raop._tcp.local."}


def _device_info_name(info: AsyncServiceInfo) -> str | None:
    if info.type not in NAME_USED_FOR_DEVICE_INFO:
        return None
    short_name = info.name[: -(len(info.type) + 1)]
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

    async def process(self, timeout: int) -> None:
        """Start to process devices and services."""
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
        short_names: set[str] = set()
        for info in infos:
            if short_name := _device_info_name(info):
                short_names.add(short_name)
        device_infos: dict[str, AsyncServiceInfo] = {}
        if short_names:
            device_infos = {
                name: AsyncServiceInfo(DEVICE_INFO_TYPE, f"{name}.{DEVICE_INFO_TYPE}")
                for name in short_names
            }
            await asyncio.gather(
                *[
                    info.async_request(
                        zeroconf, zc_timeout, question_type=DNSQuestionType.QU
                    )
                    for info in device_infos.values()
                ]
            )
        services_by_address: dict[str, list[AsyncServiceInfo]] = {}
        name_by_address: dict[str, str] = {}

        for info in infos:
            if address := _first_non_link_local_or_v6_address(info.addresses):
                services_by_address.setdefault(address, []).append(info)
                if short_name := _device_info_name(info):
                    name_by_address[address] = short_name

        for address, services in services_by_address.items():
            if self.hosts and address not in self.hosts:
                continue
            is_sleep_proxy = all(service.port == 0 for service in services)
            atv_services = []
            model = None
            for service in services:
                atv_type = service.type[:-1]
                name = info.name[: -(len(info.type) + 1)]
                if model is None and (
                    device_info := service.properties.get(short_name)
                ):
                    if possible_model := device_info.properties.get(b"model"):
                        with contextlib.suppress(UnicodeDecodeError):
                            model = possible_model.decode("utf-8")
                try:
                    decoded_properties = {
                        k.decode("ascii"): v.decode("utf-8")
                        for k, v in service.properties
                    }
                except UnicodeDecodeError:
                    continue
                atv_services.append(
                    mdns.Service(atv_type, name, address, info.port, decoded_properties)
                )
            self.handle_response(
                mdns.Response(
                    service=atv_services, deep_sleep=is_sleep_proxy, model=model
                )
            )


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
