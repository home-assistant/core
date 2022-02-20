"""Network helper class for the network integration."""
from __future__ import annotations

from ipaddress import IPv4Address, IPv6Address, ip_address
import logging
import socket
from typing import cast

import ifaddr

from homeassistant.core import callback

from .const import MDNS_TARGET_IP
from .models import Adapter, IPv4ConfiguredAddress, IPv6ConfiguredAddress

_LOGGER = logging.getLogger(__name__)


async def async_load_adapters() -> list[Adapter]:
    """Load adapters."""
    source_ip = async_get_source_ip(MDNS_TARGET_IP)
    source_ip_address = ip_address(source_ip) if source_ip else None

    ha_adapters: list[Adapter] = [
        _ifaddr_adapter_to_ha(adapter, source_ip_address)
        for adapter in ifaddr.get_adapters()
    ]

    if not any(adapter["default"] and adapter["auto"] for adapter in ha_adapters):
        for adapter in ha_adapters:
            if _adapter_has_external_address(adapter):
                adapter["auto"] = True

    return ha_adapters


def enable_adapters(adapters: list[Adapter], enabled_interfaces: list[str]) -> bool:
    """Enable configured adapters."""
    _reset_enabled_adapters(adapters)

    if not enabled_interfaces:
        return False

    found_adapter = False
    for adapter in adapters:
        if adapter["name"] in enabled_interfaces:
            adapter["enabled"] = True
            found_adapter = True

    return found_adapter


def enable_auto_detected_adapters(adapters: list[Adapter]) -> None:
    """Enable auto detected adapters."""
    enable_adapters(
        adapters, [adapter["name"] for adapter in adapters if adapter["auto"]]
    )


def _adapter_has_external_address(adapter: Adapter) -> bool:
    """Adapter has a non-loopback and non-link-local address."""
    return any(
        _has_external_address(v4_config["address"]) for v4_config in adapter["ipv4"]
    ) or any(
        _has_external_address(v6_config["address"]) for v6_config in adapter["ipv6"]
    )


def _has_external_address(ip_str: str) -> bool:
    return _ip_address_is_external(ip_address(ip_str))


def _ip_address_is_external(ip_addr: IPv4Address | IPv6Address) -> bool:
    return (
        not ip_addr.is_multicast
        and not ip_addr.is_loopback
        and not ip_addr.is_link_local
    )


def _reset_enabled_adapters(adapters: list[Adapter]) -> None:
    for adapter in adapters:
        adapter["enabled"] = False


def _ifaddr_adapter_to_ha(
    adapter: ifaddr.Adapter, next_hop_address: None | IPv4Address | IPv6Address
) -> Adapter:
    """Convert an ifaddr adapter to ha."""
    ip_v4s: list[IPv4ConfiguredAddress] = []
    ip_v6s: list[IPv6ConfiguredAddress] = []
    default = False
    auto = False

    for ip_config in adapter.ips:
        if ip_config.is_IPv6:
            ip_addr = ip_address(ip_config.ip[0])
            ip_v6s.append(_ip_v6_from_adapter(ip_config))
        else:
            ip_addr = ip_address(ip_config.ip)
            ip_v4s.append(_ip_v4_from_adapter(ip_config))

        if ip_addr == next_hop_address:
            default = True
            if _ip_address_is_external(ip_addr):
                auto = True

    return {
        "name": adapter.nice_name,
        "index": adapter.index,
        "enabled": False,
        "auto": auto,
        "default": default,
        "ipv4": ip_v4s,
        "ipv6": ip_v6s,
    }


def _ip_v6_from_adapter(ip_config: ifaddr.IP) -> IPv6ConfiguredAddress:
    return {
        "address": ip_config.ip[0],
        "flowinfo": ip_config.ip[1],
        "scope_id": ip_config.ip[2],
        "network_prefix": ip_config.network_prefix,
    }


def _ip_v4_from_adapter(ip_config: ifaddr.IP) -> IPv4ConfiguredAddress:
    return {
        "address": ip_config.ip,
        "network_prefix": ip_config.network_prefix,
    }


@callback
def async_get_source_ip(target_ip: str) -> str | None:
    """Return the source ip that will reach target_ip."""
    test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    test_sock.setblocking(False)  # must be non-blocking for async
    try:
        test_sock.connect((target_ip, 1))
        return cast(str, test_sock.getsockname()[0])
    except Exception:  # pylint: disable=broad-except
        _LOGGER.debug(
            "The system could not auto detect the source ip for %s on your operating system",
            target_ip,
        )
        return None
    finally:
        test_sock.close()
