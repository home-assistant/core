"""The Network Configuration integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.loader import bind_hass

from .const import ATTR_ADAPTERS, ATTR_CONFIGURED_ADAPTERS, DOMAIN, INTERFACES_SCHEMA
from .models import Adapter
from .network import Network

ZEROCONF_DOMAIN = "zeroconf"


@bind_hass
async def async_get_adapters(hass: HomeAssistant) -> list[Adapter]:
    """Get the network adapter configuration."""
    network: Network = hass.data[DOMAIN]
    return network.adapters


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up network for Home Assistant."""

    hass.data[DOMAIN] = network = Network(hass)
    await network.async_setup()
    await network.async_migrate_from_zeroconf(config.get(ZEROCONF_DOMAIN, {}))
    network.async_configure()

    websocket_api.async_register_command(hass, websocket_network)
    websocket_api.async_register_command(hass, websocket_network_adapters)

    return True


@websocket_api.require_admin  # type: ignore[arg-type]
@websocket_api.async_response
@websocket_api.websocket_command({vol.Required("type"): "network"})
async def websocket_network(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
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


@websocket_api.require_admin  # type: ignore[arg-type]
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required("type"): "network/adapters",
        vol.Required("config", default={}): INTERFACES_SCHEMA,
    }
)
async def websocket_network_adapters(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict,
) -> None:
    """Update network config."""
    network: Network = hass.data[DOMAIN]

    await network.async_save(msg[ATTR_CONFIGURED_ADAPTERS])

    connection.send_result(
        msg["id"],
        {ATTR_CONFIGURED_ADAPTERS: network.configured_adapters},
    )
