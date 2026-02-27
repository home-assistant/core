"""DataUpdateCoordinator and UDP protocol for the EARN-E P1 Meter."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class EarnEP1UDPProtocol(asyncio.DatagramProtocol):
    """UDP protocol that receives EARN-E P1 meter JSON packets."""

    def __init__(self, coordinator: EarnEP1Coordinator, host: str) -> None:
        """Initialize the protocol."""
        self.coordinator = coordinator
        self.host = host

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Handle incoming UDP datagram."""
        source_ip = addr[0]
        if source_ip != self.host:
            return

        try:
            payload = json.loads(data)
        except (json.JSONDecodeError, UnicodeDecodeError):
            _LOGGER.warning("Failed to decode UDP packet from %s", source_ip)
            return

        if not isinstance(payload, dict):
            return

        # Extract device info from full telegrams (only set serial once
        # to keep device identifiers stable for the device registry)
        if "serial" in payload and self.coordinator.serial is None:
            self.coordinator.serial = payload["serial"]
        if "model" in payload:
            self.coordinator.model = payload["model"]
        if "swVersion" in payload:
            self.coordinator.sw_version = str(payload["swVersion"])

        # Merge new data into existing coordinator data
        merged = dict(self.coordinator.data or {})
        merged.update(payload)
        self.coordinator.async_set_updated_data(merged)

    def error_received(self, exc: Exception) -> None:
        """Handle protocol errors."""
        _LOGGER.error("UDP protocol error: %s", exc)

    def connection_lost(self, exc: Exception | None) -> None:
        """Handle connection lost."""
        if exc:
            _LOGGER.error("UDP connection lost: %s", exc)


class EarnEP1Coordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for the EARN-E P1 Meter."""

    def __init__(
        self, hass: HomeAssistant, host: str, serial: str | None = None
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
        )
        self.host = host
        self.data = {}
        self.serial: str | None = serial
        self.identifier: str = serial or host
        self.model: str | None = None
        self.sw_version: str | None = None
        self._transport: asyncio.DatagramTransport | None = None

    async def async_start(self) -> None:
        """Start listening for UDP packets."""
        loop = self.hass.loop
        transport, _ = await loop.create_datagram_endpoint(
            lambda: EarnEP1UDPProtocol(self, self.host),
            local_addr=("0.0.0.0", DEFAULT_PORT),
            allow_broadcast=True,
        )
        self._transport = transport
        _LOGGER.debug("EARN-E P1 UDP listener started on port %s", DEFAULT_PORT)

    async def async_stop(self) -> None:
        """Stop listening for UDP packets."""
        if self._transport:
            self._transport.close()
            self._transport = None
            _LOGGER.debug("EARN-E P1 UDP listener stopped")
