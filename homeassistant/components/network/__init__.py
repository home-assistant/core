"""The Network Configuration integration."""

from ipaddress import IPv4Address, IPv6Address, ip_interface
import logging
from pathlib import Path

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.typing import UNDEFINED, ConfigType, UndefinedType
from homeassistant.util import package
from homeassistant.util.network import is_ipv6_address

from . import util
from .const import (
    DOMAIN,
    IPV4_BROADCAST_ADDR,
    LOOPBACK_TARGET_IP,
    MDNS_TARGET_IP,
    PUBLIC_TARGET_IP,
    PUBLIC_TARGET_IPV6,
)
from .models import Adapter
from .network import Network, async_get_loaded_network, async_get_network

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


def _check_docker_without_host_networking() -> bool:
    """Check if we are not using host networking in Docker."""
    if not package.is_docker_env():
        # We are not in Docker, so we don't need to check for host networking
        return True

    if Path("/proc/sys/net/ipv4/ip_forward").exists():
        # If we can read this file, we likely have host networking
        return True

    return False


async def async_get_adapters(hass: HomeAssistant) -> list[Adapter]:
    """Get the network adapter configuration."""
    network: Network = await async_get_network(hass)
    return network.adapters


@callback
def async_get_loaded_adapters(hass: HomeAssistant) -> list[Adapter]:
    """Get the network adapter configuration."""
    return async_get_loaded_network(hass).adapters


async def async_get_source_ip(
    hass: HomeAssistant,
    target_ip: str | UndefinedType = UNDEFINED,
    *,
    allow_ipv6_fallback: bool = False,
) -> str:
    """Get the source IP for a target, defaulting to IPv4.

    With no target, allow_ipv6_fallback permits IPv6 when no enabled non-loopback
    IPv4 address is available. Explicit IPv6 targets always use IPv6.
    """
    adapters = await async_get_adapters(hass)
    sources = async_get_enabled_source_ips_from_adapters(adapters)
    all_ipv4s = [str(ip) for ip in sources if isinstance(ip, IPv4Address)]

    ipv6_target = (
        IPv6Address(target_ip)
        if target_ip is not UNDEFINED and is_ipv6_address(target_ip)
        else None
    )
    if ipv6_target is not None or (
        target_ip is UNDEFINED
        and allow_ipv6_fallback
        and not any(
            isinstance(ip, IPv4Address) and not ip.is_loopback for ip in sources
        )
    ):
        destination = ipv6_target or IPv6Address(PUBLIC_TARGET_IPV6)
        if destination.is_link_local:
            sources = [
                ip
                for adapter in adapters
                for ip in async_get_enabled_source_ips_from_adapters([adapter])
                if isinstance(ip, IPv6Address)
                and destination.scope_id in (adapter["name"], ip.scope_id)
            ]
        all_ipv6s = [
            str(ip) if ip.is_link_local else str(IPv6Address(ip.packed))
            for ip in sources
            if isinstance(ip, IPv6Address)
            and not ip.is_unspecified
            and not ip.is_multicast
            and ip.is_link_local == destination.is_link_local
            and ip.is_loopback == destination.is_loopback
        ]
        if all_ipv6s:
            source_ip = util.async_get_source_ip(str(destination))
            return source_ip if source_ip in all_ipv6s else all_ipv6s[0]
        if ipv6_target is not None:
            raise HomeAssistantError("No enabled IPv6 source address for the target")

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
            "Because the system does not have any enabled IPv4 addresses, source"
            " address detection may be inaccurate"
        )
        if source_ip is None:
            raise HomeAssistantError(
                "Could not determine source ip because the system does not have any"
                " enabled IPv4 addresses and creating a socket failed"
            )
        return source_ip

    return source_ip if source_ip in all_ipv4s else all_ipv4s[0]


async def async_get_enabled_source_ips(
    hass: HomeAssistant,
) -> list[IPv4Address | IPv6Address]:
    """Build the list of enabled source ips."""
    return async_get_enabled_source_ips_from_adapters(await async_get_adapters(hass))


@callback
def async_get_enabled_source_ips_from_adapters(
    adapters: list[Adapter],
) -> list[IPv4Address | IPv6Address]:
    """Build the list of enabled source ips."""
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


async def async_get_announce_addresses(hass: HomeAssistant) -> list[str]:
    """Return a list of IP addresses to announce/use via zeroconf/ssdp/etc.

    The default IPv4 address is returned first when IPv4 is enabled.
    """
    adapters = await async_get_adapters(hass)
    addresses: list[str] = []
    has_ipv4 = False
    for adapter in adapters:
        if not adapter["enabled"]:
            continue
        has_ipv4 = has_ipv4 or bool(adapter["ipv4"])
        addresses.extend(str(IPv4Address(ips["address"])) for ips in adapter["ipv4"])
        addresses.extend(str(IPv6Address(ips["address"])) for ips in adapter["ipv6"])

    if not has_ipv4:
        return addresses

    # Puts the default IPv4 address first in the list to preserve compatibility,
    # because some mDNS implementations ignores anything but the first announced
    # address.
    if default_ip := await async_get_source_ip(hass, target_ip=MDNS_TARGET_IP):
        if default_ip in addresses:
            addresses.remove(default_ip)
        return [default_ip, *addresses]
    return list(addresses)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up network for Home Assistant."""
    # Avoid circular issue: http->network->websocket_api->http
    from .websocket import async_register_websocket_commands  # noqa: PLC0415

    await async_get_network(hass)

    if not await hass.async_add_executor_job(_check_docker_without_host_networking):
        docs_url = "https://docs.docker.com/network/network-tutorial-host/"
        install_url = "https://www.home-assistant.io/installation/linux#install-home-assistant-container"
        ir.async_create_issue(
            hass,
            DOMAIN,
            "docker_host_network",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="docker_host_network",
            learn_more_url=install_url,
            translation_placeholders={"docs_url": docs_url, "install_url": install_url},
        )

    async_register_websocket_commands(hass)
    return True
