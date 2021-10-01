"""The Network Configuration integration."""
from __future__ import annotations

from ipaddress import IPv4Address, IPv6Address, ip_interface
import logging

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass

from . import util
from .const import (
    ATTR_ADAPTERS,
    ATTR_CONFIGURED_ADAPTERS,
    DOMAIN,
    IPV4_BROADCAST_ADDR,
    NETWORK_CONFIG_SCHEMA,
)
from .models import Adapter
from .network import Network

ZEROCONF_DOMAIN = "zeroconf"  # cannot import from zeroconf due to circular dep
_LOGGER = logging.getLogger(__name__)


@bind_hass
async def async_get_adapters(hass: HomeAssistant) -> list[Adapter]:
    """Get the network adapter configuration."""
    network: Network = hass.data[DOMAIN]
    return network.adapters


@bind_hass
async def async_get_source_ip(hass: HomeAssistant, target_ip: str) -> str:
    """Get the source ip for a target ip."""
    adapters = await async_get_adapters(hass)
    all_ipv4s = []
    for adapter in adapters:
        if adapter["enabled"] and (ipv4s := adapter["ipv4"]):
            all_ipv4s.extend([ipv4["address"] for ipv4 in ipv4s])

    source_ip = util.async_get_source_ip(target_ip)
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
            sources.extend(IPv4Address(ipv4["address"]) for ipv4 in adapter["ipv4"])
        if adapter["ipv6"]:
            # With python 3.9 add scope_ids can be
            # added by enumerating adapter["ipv6"]s
            # IPv6Address(f"::%{ipv6['scope_id']}")
            sources.extend(IPv6Address(ipv6["address"]) for ipv6 in adapter["ipv6"])

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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up network for Home Assistant."""

    hass.data[DOMAIN] = network = Network(hass)
    await network.async_setup()
    if ZEROCONF_DOMAIN in config:
        await network.async_migrate_from_zeroconf(config[ZEROCONF_DOMAIN])
    network.async_configure()

    _LOGGER.debug("Adapters: %s", network.adapters)

    websocket_api.async_register_command(hass, websocket_network_adapters)
    websocket_api.async_register_command(hass, websocket_network_adapters_configure)

    return True


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "network"})
@websocket_api.async_response
async def websocket_network_adapters(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
) -> None:
    """Return network preferences."""
    network: Network = hass.data[DOMAIN]
    connection.send_result(
        msg["id"],
        {
            ATTR_ADAPTERS: network.adapters,
            ATTR_CONFIGURED_ADAPTERS: network.configured_adapters,
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "network/configure",
        vol.Required("config", default={}): NETWORK_CONFIG_SCHEMA,
    }
)
@websocket_api.async_response
async def websocket_network_adapters_configure(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
) -> None:
    """Update network config."""
    network: Network = hass.data[DOMAIN]

    await network.async_reconfig(msg["config"])

    connection.send_result(
        msg["id"],
        {ATTR_CONFIGURED_ADAPTERS: network.configured_adapters},
    )
