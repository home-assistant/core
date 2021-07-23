"""The Network Configuration integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass

from . import util
from .const import (
    ATTR_ADAPTERS,
    ATTR_CONFIGURED_ADAPTERS,
    DOMAIN,
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
