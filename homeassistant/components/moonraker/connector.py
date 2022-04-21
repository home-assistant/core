"""Moonrake API connector."""
from __future__ import annotations

import asyncio
import json
import logging
from random import randrange
from typing import Any

from aiohttp import ClientConnectionError, ClientSession
from moonraker_api import MoonrakerClient, MoonrakerListener
from moonraker_api.const import (
    WEBSOCKET_STATE_CONNECTED,
    WEBSOCKET_STATE_CONNECTING,
    WEBSOCKET_STATE_STOPPED,
)
from moonraker_api.websockets.websocketclient import ClientNotAuthenticatedError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    BACKOFF_MAX_COUNT,
    BACKOFF_TIME_LOWER_LIMIT,
    BACKOFF_TIME_UPPER_LIMIT,
    SIGNAL_STATE_AVAILABLE,
    SIGNAL_UPDATE_MODULE,
    SIGNAL_UPDATE_RATE_LIMIT,
)

_LOGGER = logging.getLogger(__name__)


def generate_signal(signal_name: str, entry_id: str) -> str:
    """Generate a unique signal name."""
    return f"{signal_name}_{entry_id}"


class APIConnector(MoonrakerListener):
    """Connector class to manage common interface and properties."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: ClientSession,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the class."""
        self.hass = hass
        self.running = False
        self.retry_count = 0
        self.cache: dict[str, Any] = {}
        self.entry = config_entry
        self.client = MoonrakerClient(
            self,
            config_entry.data[CONF_HOST],
            config_entry.data[CONF_PORT],
            config_entry.data[CONF_API_KEY],
            config_entry.data[CONF_SSL],
            loop=hass.loop,
            session=session,
            timeout=30,
        )

    async def start(self) -> None:
        """Start the websocket connection and set as running."""
        _LOGGER.info("Starting API connection for (%s)", self.entry.data[CONF_HOST])
        self.running = True
        await self._start()

    async def _start(self, _now: Any = None) -> None:
        """Start the websocket connection."""
        try:
            await self.client.connect()
        except ClientNotAuthenticatedError:
            _LOGGER.warning(
                "Authentication failed to Moonraker API for %s",
                self.entry.data[CONF_HOST],
            )
            self.entry.async_start_reauth(self.hass)
        except ClientConnectionError:
            _LOGGER.warning(
                "Unable to connect to Moonraker API for %s",
                self.entry.data[CONF_HOST],
            )
        except asyncio.TimeoutError:
            _LOGGER.warning(
                "Timeout trying to connect to Moonraker API for %s",
                self.entry.data[CONF_HOST],
            )

    async def stop(self) -> None:
        """Stop the websocket connection."""
        self.running = False
        _LOGGER.info("Stopping API connection for (%s)", self.entry.data[CONF_HOST])
        await self.client.disconnect()

    async def state_changed(self, state: str) -> None:
        """Notifies of changing websocket state."""
        _LOGGER.debug("Stated changed to %s (%s)", state, self.entry.data[CONF_HOST])
        if state == WEBSOCKET_STATE_CONNECTING:
            self.retry_count += 1
        elif state == WEBSOCKET_STATE_CONNECTED:
            self.retry_count = 0
            if await self.client.get_klipper_status() == "ready":
                await self._do_ready_handling()
        elif state == WEBSOCKET_STATE_STOPPED:
            async_dispatcher_send(
                self.hass,
                generate_signal(SIGNAL_STATE_AVAILABLE, self.entry.entry_id),
                False,
            )
            if self.running:
                max_backoff_count = min(BACKOFF_MAX_COUNT, self.retry_count)
                backoff = min(
                    max(
                        randrange(2**max_backoff_count),
                        BACKOFF_TIME_LOWER_LIMIT,
                    ),
                    BACKOFF_TIME_UPPER_LIMIT,
                )
                _LOGGER.info(
                    "Unable to connect to (%s), backing off for %d seconds",
                    self.entry.data[CONF_HOST],
                    backoff,
                )
                self.hass.helpers.event.async_call_later(backoff, self._start)

    async def on_exception(self, exception: BaseException) -> None:
        """Notifies of exceptions from the websocket run loop."""
        _LOGGER.error(
            "Moonraker API error %s (%s)", str(exception), self.entry.data[CONF_HOST]
        )
        if isinstance(exception, ClientNotAuthenticatedError):
            self.entry.async_start_reauth(self.hass)

    async def on_notification(self, method: str, data: Any) -> None:
        """Notifies of state updates."""
        _LOGGER.debug(
            "Received notification %s (%s)", method, self.entry.data[CONF_HOST]
        )

        # Subscription notifications
        if method == "notify_status_update":
            message = data[0]
            timestamp = data[1]
            for module, state in message.items():
                if module in self.cache and module in [
                    "extruder",
                    "heater_bed",
                ]:
                    if timestamp - self.cache[module][1] < SIGNAL_UPDATE_RATE_LIMIT:
                        continue
                self.cache[module] = [module, timestamp]
                signal = generate_signal(
                    SIGNAL_UPDATE_MODULE % module, self.entry.entry_id
                )
                async_dispatcher_send(self.hass, signal, state)

        # Klippy status notifications
        elif method == "notify_klippy_ready":
            await self._do_ready_handling()
        elif method in ["notify_klippy_disconnected", "notify_klippy_shutdown"]:
            async_dispatcher_send(
                self.hass,
                generate_signal(SIGNAL_STATE_AVAILABLE, self.entry.entry_id),
                False,
            )

    async def _do_ready_handling(self) -> None:
        """Set status as available and request subscriptions."""
        subscriptions = {
            "extruder": ["temperature", "target"],
            "heater_bed": ["temperature", "target"],
            "virtual_sdcard": ["progress"],
            "print_stats": ["filename", "print_duration", "state"],
        }
        supported_modules = await self.client.get_supported_modules()
        available = {
            key: val for key, val in subscriptions.items() if key in supported_modules
        }
        _LOGGER.info(
            "Fetching initial state for printer sensors (%s)",
            self.entry.data[CONF_HOST],
        )
        printer_state = await self.client.call_method(
            "printer.objects.query", objects=available
        )
        if status := printer_state.get("status"):
            for module, state in status.items():
                signal = generate_signal(
                    SIGNAL_UPDATE_MODULE % module, self.entry.entry_id
                )
                async_dispatcher_send(self.hass, signal, state)

        _LOGGER.info(
            "Requesting subscriptions to printer state (%s)", self.entry.data[CONF_HOST]
        )
        _LOGGER.debug(
            "Subscriptions for (%s) %s",
            self.entry.data[CONF_HOST],
            json.dumps(available),
        )
        await self.client.call_method("printer.objects.subscribe", objects=available)
        async_dispatcher_send(
            self.hass,
            generate_signal(SIGNAL_STATE_AVAILABLE, self.entry.entry_id),
            True,
        )
