"""The Network Configuration integration."""
from __future__ import annotations

from ipaddress import (
    IPv4Address,
    IPv4Network,
    IPv6Address,
    IPv6Network,
    ip_address,
    ip_interface,
)
import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import UNDEFINED, ConfigType, UndefinedType
from homeassistant.loader import bind_hass

from . import util
from .const import (
    IPV4_BROADCAST_ADDR,
    LOOPBACK_TARGET_IP,
    MDNS_TARGET_IP,
    PUBLIC_TARGET_IP,
)
from .models import Adapter
from .network import Network, async_get_network

_LOGGER = logging.getLogger(__name__)


@bind_hass
async def async_get_adapters(hass: HomeAssistant) -> list[Adapter]:
    """Get the network adapter configuration."""
    network: Network = await async_get_network(hass)
    return network.adapters


@bind_hass
async def async_get_source_ip(
    hass: HomeAssistant, target_ip: str | UndefinedType = UNDEFINED
) -> str:
    """Get the source ip for a target ip."""
    adapters = await async_get_adapters(hass)
    all_ipv4s = []
    for adapter in adapters:
        if adapter["enabled"] and (ipv4s := adapter["ipv4"]):
            all_ipv4s.extend([ipv4["address"] for ipv4 in ipv4s])

    if target_ip is UNDEFINED:
        source_ip = (
            util.async_get_source_ip(PUBLIC_TARGET_IP)
            or util.async_get_source_ip(MDNS_TARGET_IP)
            or util.async_get_source_ip(LOOPBACK_TARGET_IP)
        )
    else:
        source_ip = util.async_get_source_ip(target_ip)

    if not all_ipv4s:
        _LOGGER.warning(
            "Because the system does not have any enabled IPv4 addresses, source address detection may be inaccurate"
        )
        if source_ip is None:
            raise HomeAssistantError(
                "Could not determine source ip because the system does not have any enabled IPv4 addresses and creating a socket failed"
            )
        return source_ip

    return source_ip if source_ip in all_ipv4s else all_ipv4s[0]


@bind_hass
async def async_get_enabled_source_ips(
    hass: HomeAssistant,
) -> list[IPv4Address | IPv6Address]:
    """Build the list of enabled source ips."""
    adapters = await async_get_adapters(hass)
    sources: list[IPv4Address | IPv6Address] = []
    for adapter in adapters:
        if not adapter["enabled"]:
            continue
        if adapter["ipv4"]:
            addrs_ipv4 = [IPv4Address(ipv4["address"]) for ipv4 in adapter["ipv4"]]
            sources.extend(addrs_ipv4)
        if adapter["ipv6"]:
            addrs_ipv6 = [
                IPv6Address(f"{ipv6['address']}%{ipv6['scope_id']}")
                for ipv6 in adapter["ipv6"]
            ]
            sources.extend(addrs_ipv6)

    return sources


@callback
def async_only_default_interface_enabled(adapters: list[Adapter]) -> bool:
    """Check to see if any non-default adapter is enabled."""
    return not any(
        adapter["enabled"] and not adapter["default"] for adapter in adapters
    )


@bind_hass
async def async_get_ipv4_broadcast_addresses(hass: HomeAssistant) -> set[IPv4Address]:
    """Return a set of broadcast addresses."""
    broadcast_addresses: set[IPv4Address] = {IPv4Address(IPV4_BROADCAST_ADDR)}
    adapters = await async_get_adapters(hass)
    if async_only_default_interface_enabled(adapters):
        return broadcast_addresses
    for adapter in adapters:
        if not adapter["enabled"]:
            continue
        for ip_info in adapter["ipv4"]:
            interface = ip_interface(
                f"{ip_info['address']}/{ip_info['network_prefix']}"
            )
            broadcast_addresses.add(
                IPv4Address(interface.network.broadcast_address.exploded)
            )
    return broadcast_addresses


async def async_ip_on_same_subnet(
    hass: HomeAssistant, ip_to_check: str | IPv4Address | IPv6Address
) -> bool:
    """Check if an ip address is on the same subnet as one of the configured network addresses."""
    adapters = await async_get_adapters(hass)
    ip_addr = ip_address(ip_to_check)
    for adapter in adapters:
        if not adapter["enabled"]:
            continue
        if ip_addr.version == 4:
            for ip_info in adapter["ipv4"]:
                if ip_addr in IPv4Network(
                    f"{ip_info['address']}/{ip_info['network_prefix']}", strict=False
                ):
                    return True
        if ip_addr.version == 6:
            for ip_info in adapter["ipv6"]:
                if ip_addr in IPv6Network(
                    f"{ip_info['address']}/{ip_info['network_prefix']}", strict=False
                ):
                    return True
    return False


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up network for Home Assistant."""
    # Avoid circular issue: http->network->websocket_api->http
    from .websocket import (  # pylint: disable=import-outside-toplevel
        async_register_websocket_commands,
    )

    async_register_websocket_commands(hass)
    return True
