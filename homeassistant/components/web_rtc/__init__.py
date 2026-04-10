"""The WebRTC integration."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

import voluptuous as vol
from webrtc_models import RTCIceServer

from homeassistant.components import websocket_api
from homeassistant.const import CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.core_config import (
    CONF_CREDENTIAL,
    CONF_ICE_SERVERS,
    validate_stun_or_turn_url,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

__all__ = [
    "async_get_ice_servers",
    "async_register_ice_servers",
]

DOMAIN = "web_rtc"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_ICE_SERVERS): vol.All(
                    cv.ensure_list,
                    [
                        vol.Schema(
                            {
                                vol.Required(CONF_URL): vol.All(
                                    cv.ensure_list, [validate_stun_or_turn_url]
                                ),
                                vol.Optional(CONF_USERNAME): cv.string,
                                vol.Optional(CONF_CREDENTIAL): cv.string,
                            }
                        )
                    ],
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

DATA_ICE_SERVERS_USER: HassKey[Iterable[RTCIceServer]] = HassKey(
    "web_rtc_ice_servers_user"
)
DATA_ICE_SERVERS: HassKey[list[Callable[[], Iterable[RTCIceServer]]]] = HassKey(
    "web_rtc_ice_servers"
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the WebRTC integration."""
    servers = [
        RTCIceServer(
            server[CONF_URL],
            server.get(CONF_USERNAME),
            server.get(CONF_CREDENTIAL),
        )
        for server in config.get(DOMAIN, {}).get(CONF_ICE_SERVERS, [])
    ]
    if servers:
        hass.data[DATA_ICE_SERVERS_USER] = servers

    hass.data[DATA_ICE_SERVERS] = []
    websocket_api.async_register_command(hass, ws_ice_servers)
    return True


@callback
def async_register_ice_servers(
    hass: HomeAssistant,
    get_ice_server_fn: Callable[[], Iterable[RTCIceServer]],
) -> Callable[[], None]:
    """Register an ICE server.

    The registering integration is responsible to implement caching if needed.
    """
    servers = hass.data[DATA_ICE_SERVERS]

    def remove() -> None:
        servers.remove(get_ice_server_fn)

    servers.append(get_ice_server_fn)
    return remove


@callback
def async_get_ice_servers(hass: HomeAssistant) -> list[RTCIceServer]:
    """Return all registered ICE servers."""
    servers: list[RTCIceServer] = []

    if hass.config.webrtc.ice_servers:
        servers.extend(hass.config.webrtc.ice_servers)

    if DATA_ICE_SERVERS_USER in hass.data:
        servers.extend(hass.data[DATA_ICE_SERVERS_USER])

    if not servers:
        servers = [
            RTCIceServer(
                urls=[
                    "stun:stun.home-assistant.io:3478",
                    "stun:stun.home-assistant.io:80",
                ]
            ),
        ]

    for gen_servers in hass.data[DATA_ICE_SERVERS]:
        servers.extend(gen_servers())

    return servers


@websocket_api.websocket_command(
    {
        "type": "web_rtc/ice_servers",
    }
)
@callback
def ws_ice_servers(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle get WebRTC ICE servers websocket command."""
    ice_servers = [server.to_dict() for server in async_get_ice_servers(hass)]
    connection.send_result(msg["id"], ice_servers)
