"""Passive discovery helpers for the Sony Projector integration."""

from __future__ import annotations

import asyncio
import logging
import socket
from typing import Any

import pysdcp_extended

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import discovery_flow

from .const import (
    CONF_MODEL,
    CONF_SERIAL,
    CONF_TITLE,
    DATA_DISCOVERY,
    DEFAULT_NAME,
    DISCOVERY_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class SonyProjectorDiscoveryProtocol(asyncio.DatagramProtocol):
    """Protocol that listens for SDCP discovery broadcasts."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the discovery protocol."""

        self._hass = hass
        self._transport: asyncio.DatagramTransport | None = None
        self._seen: set[str] = set()

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """Store the created transport."""

        self._transport = transport  # type: ignore[assignment]
        sock = transport.get_extra_info("socket")
        if isinstance(sock, socket.socket):
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            except OSError:
                _LOGGER.debug("Failed to enable address reuse for SDCP listener")

    def connection_lost(self, exc: Exception | None) -> None:
        """Handle the datagram connection closing."""

        if exc is not None:
            _LOGGER.debug("SDCP discovery listener closed: %s", exc)
        self._transport = None

    def error_received(self, exc: Exception) -> None:
        """Log socket errors raised by the transport."""

        _LOGGER.debug("SDCP discovery listener error: %s", exc)

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Handle an incoming SDCP discovery broadcast."""

        host, _port = addr
        try:
            _header, info = pysdcp_extended.process_SDAP(data)
        except Exception:  # noqa: BLE001 - library raises broad exceptions
            _LOGGER.debug("Ignoring non-SDAP datagram from %s", host)
            return

        serial = str(info.serial_number) if info.serial_number else None
        model = info.product_name or None
        if serial is not None:
            title = model or serial
        else:
            title = DEFAULT_NAME

        dedupe_key = serial or host
        if dedupe_key in self._seen:
            return
        self._seen.add(dedupe_key)

        _LOGGER.debug("Discovered Sony projector %s (%s) at %s", title, serial, host)

        discovery_flow.async_create_flow(
            self._hass,
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data={
                CONF_HOST: host,
                CONF_SERIAL: serial,
                CONF_MODEL: model,
                CONF_TITLE: title,
            },
        )

    @callback
    def async_close(self) -> None:
        """Close the underlying UDP transport."""

        if self._transport is not None:
            self._transport.close()
            self._transport = None


async def async_start_listener(
    hass: HomeAssistant,
) -> SonyProjectorDiscoveryProtocol | None:
    """Start listening for passive SDCP discovery broadcasts."""

    loop = asyncio.get_running_loop()
    protocol = SonyProjectorDiscoveryProtocol(hass)

    try:
        await loop.create_datagram_endpoint(
            lambda: protocol,
            local_addr=("0.0.0.0", DISCOVERY_PORT),
            allow_broadcast=True,
        )
    except OSError as err:
        _LOGGER.debug("Unable to bind SDCP discovery listener: %s", err)
        return None

    @callback
    def _close_listener(_: Any) -> None:
        protocol.async_close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _close_listener)
    hass.data.setdefault(DOMAIN, {})[DATA_DISCOVERY] = protocol
    _LOGGER.debug(
        "Listening for Sony projector SDCP broadcasts on port %s", DISCOVERY_PORT
    )
    return protocol
