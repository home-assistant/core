"""Network helper class for the network integration."""
from __future__ import annotations

from collections.abc import Iterable
from ipaddress import IPv4Address, IPv6Address, ip_address
import logging
from typing import cast

import ifaddr
from pyroute2 import IPRoute

from homeassistant.core import HomeAssistant

from .const import MDNS_TARGET_IP
from .models import Adapter, IPv4ConfiguredAddress, IPv6ConfiguredAddress

_LOGGER = logging.getLogger(__name__)


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


def adapters_with_exernal_addresses(adapters: list[Adapter]) -> list[str]:
    """Enable all interfaces with an external address."""
    return [
        adapter["name"]
        for adapter in adapters
        if _adapter_has_external_address(adapter)
    ]


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


def load_adapters(next_hop: str | None) -> list[Adapter]:
    """Load adapters."""
    next_hop_address = ip_address(next_hop) if next_hop else None

    ha_adapters: list[Adapter] = [
        _ifaddr_adapter_to_ha(adapter, next_hop_address)
        for adapter in ifaddr.get_adapters()
    ]

    if not any(adapter["default"] and adapter["auto"] for adapter in ha_adapters):
        for adapter in ha_adapters:
            if _adapter_has_external_address(adapter):
                adapter["auto"] = True

    return ha_adapters


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


def _get_ip_route(dst_ip: str) -> Iterable:
    """Get ip next hop."""
    return cast(Iterable, IPRoute().route("get", dst=dst_ip))


def _first_ip_nexthop_from_route(routes: Iterable) -> str | None:
    """Find the first RTA_PREFSRC in the routes."""
    _LOGGER.debug("Routes: %s", routes)
    for route in routes:
        for key, value in route["attrs"]:
            if key == "RTA_PREFSRC":
                return cast(str, value)
    return None


async def async_default_next_broadcast_hop(hass: HomeAssistant) -> None | str:
    """Auto detect the default next broadcast hop."""
    try:
        routes: Iterable = await hass.async_add_executor_job(
            _get_ip_route, MDNS_TARGET_IP
        )
    except Exception as ex:  # pylint: disable=broad-except
        _LOGGER.debug(
            "The system could not auto detect routing data on your operating system",
            exc_info=ex,
        )
        return None
    else:
        if first_ip := _first_ip_nexthop_from_route(routes):
            return first_ip

    _LOGGER.debug(
        "The system could not auto detect the nexthop for %s on your operating system",
        MDNS_TARGET_IP,
    )
    return None
