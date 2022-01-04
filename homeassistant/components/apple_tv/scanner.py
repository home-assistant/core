"""Scanner for apple_tv that uses HomeAssistant zeroconf."""
from __future__ import annotations

import asyncio
from ipaddress import IPv4Address

from pyatv import interface
from pyatv.const import Protocol
from pyatv.core.scan import BaseScanner
from pyatv.helpers import get_unique_id
from pyatv.protocols import PROTOCOLS
from zeroconf import DNSQuestionType
from zeroconf.asyncio import AsyncServiceInfo, AsyncZeroconf

from homeassistant.components.zeroconf import DEVICE_INFO_TYPE, async_get_async_instance
from homeassistant.core import HomeAssistant

NAME_USED_FOR_DEVICE_INFO = {"_airplay._tcp.local.", "_raop._tcp.local."}


class ZeroconfScanner(BaseScanner):
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
        self.hosts = hosts
        self.identifier = identifier
        self.loop = asyncio.get_running_loop()

    async def process(self, timeout: int) -> None:
        """Start to process devices and services."""
        infos: list[AsyncServiceInfo] = []
        zc_timeout = timeout * 1000
        zeroconf = self.zc.zeroconf
        zc_types = [f"{service}." for service in self._services]
        infos = [
            AsyncServiceInfo(zc_type, record.alias)
            for zc_type in zc_types
            for record in zeroconf.cache.entries_with_name(zc_type)
        ]
        await asyncio.gather(
            *[info.async_request(zeroconf, zc_timeout) for info in infos]
        )
        short_names: set[str] = set()
        for info in infos:
            if info.type in NAME_USED_FOR_DEVICE_INFO:
                short_name = info.name[: len(info.type)]
                if "@" in short_name:
                    short_name = short_name.split("@")[1]
                short_names.add(short_name)
        device_infos = []
        if short_names:
            device_infos = [
                AsyncServiceInfo(DEVICE_INFO_TYPE, f"{name}.{DEVICE_INFO_TYPE}")
                for name in short_names
            ]
            await asyncio.gather(
                *[
                    info.async_request(
                        zeroconf, zc_timeout, question_type=DNSQuestionType.QU
                    )
                    for info in device_infos
                ]
            )
        import pprint

        pprint.pprint([infos, device_infos])


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
        scanner = ZeroconfScanner(
            zc=async_zc, hosts=[IPv4Address(host) for host in hosts]
        )
    else:
        scanner = ZeroconfScanner(zc=async_zc, identifier=identifier)

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
