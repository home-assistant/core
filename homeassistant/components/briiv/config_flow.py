"""The Briiv Air Purifier integration."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import json
import logging
import socket
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError

LOGGER = logging.getLogger(__name__)
DOMAIN = "briiv"
PLATFORMS = [Platform.SENSOR]


class BriivError(HomeAssistantError):
    """Base error for Briiv integration."""


class BriivAPI:
    """API class to handle UDP communication with Briiv device."""

    def __init__(self, host: str = "0.0.0.0", port: int = 3334) -> None:
        """Initialize the API."""
        self.host = host
        self.port = port
        self.sock: socket.socket | None = None
        self._callbacks: list[Callable[[dict[str, Any]], Awaitable[None]]] = []
        self._is_running = True

    async def start_listening(self, loop: asyncio.AbstractEventLoop) -> None:
        """Start listening for UDP packets."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, self.port))
        self.sock.setblocking(False)

        while self._is_running:
            try:
                data, _ = await loop.sock_recvfrom(self.sock, 1024)
                try:
                    json_data = json.loads(data.decode())
                    for callback in self._callbacks:
                        await callback(json_data)
                except json.JSONDecodeError:
                    LOGGER.error("Error decoding JSON data")
                except HomeAssistantError as err:
                    LOGGER.error("Error processing data: %s", err)
            except OSError as err:
                if self._is_running:
                    LOGGER.error("Socket error: %s", err)
                    await asyncio.sleep(1)

    def register_callback(self, callback) -> None:
        """Register callback for data updates."""
        self._callbacks.append(callback)

    def remove_callback(self, callback) -> None:
        """Remove callback from updates."""
        self._callbacks.remove(callback)

    async def stop_listening(self) -> None:
        """Stop listening and close socket."""
        self._is_running = False
        if self.sock:
            self.sock.close()
            self.sock = None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Briiv from a config entry."""
    api = BriivAPI(
        host=entry.data.get("host", "0.0.0.0"), port=entry.data.get("port", 3334)
    )

    try:
        # Start the UDP listener
        hass.loop.create_task(api.start_listening(hass.loop))
    except OSError as err:
        raise ConfigEntryNotReady from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = api
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    api: BriivAPI = hass.data[DOMAIN][entry.entry_id]
    await api.stop_listening()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
