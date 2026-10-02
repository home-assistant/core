"""Manage the UniFi Network API session and reconnect policy."""

import asyncio
from collections.abc import Callable

import aiounifi

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from ..const import LOGGER
from .backoff import BackoffPolicy


class UnifiConnectionManager:
    """Own the API session state independently of its update transports."""

    def __init__(
        self, hass: HomeAssistant, api: aiounifi.Controller, signal: str
    ) -> None:
        """Initialize the manager."""
        self.hass = hass
        self.api = api
        self.signal = signal
        self.available = True

        self._backoff = BackoffPolicy()
        self._attempt = 0
        self._retry_handle: asyncio.TimerHandle | None = None
        self._reconnect_task: asyncio.Task[None] | None = None
        self._reconnect_callback: Callable[[], None] | None = None

    @callback
    def set_reconnect_callback(self, callback_fn: Callable[[], None] | None) -> None:
        """Set the callback used to restart push transports after login."""
        self._reconnect_callback = callback_fn

    @callback
    def report_failure(
        self, err: Exception | None = None, *, log: bool = False
    ) -> None:
        """Mark the shared session unavailable and schedule one retry."""
        if self._retry_handle is not None or (
            self._reconnect_task is not None and not self._reconnect_task.done()
        ):
            return

        if self.available:
            self.available = False
            async_dispatcher_send(self.hass, self.signal)

        self._schedule_retry(log=log)
        if err is not None:
            LOGGER.debug("Schedule reconnect to UniFi Network '%s'", err)

    def _schedule_retry(self, *, log: bool = False) -> None:
        """Schedule the next session login attempt."""
        delay = self._backoff.next_delay(self._attempt)
        self._attempt += 1
        self._retry_handle = self.hass.loop.call_later(
            delay, self._async_reconnect, log
        )

    @callback
    def _async_reconnect(self, log: bool = False) -> None:
        """Try to restore the API session."""
        self._retry_handle = None
        if self._reconnect_task is not None and not self._reconnect_task.done():
            return

        async def _reconnect() -> None:
            if log:
                LOGGER.info("Will try to reconnect to UniFi Network")
            try:
                async with asyncio.timeout(5):
                    await self.api.login()
            except (
                TimeoutError,
                aiounifi.BadGateway,
                aiounifi.ServiceUnavailable,
                aiounifi.AiounifiException,
            ) as err:
                self._reconnect_task = None
                LOGGER.debug("Schedule reconnect to UniFi Network '%s'", err)
                self._schedule_retry()
            else:
                self._reconnect_task = None
                self._attempt = 0
                self._set_available(True)
                if self._reconnect_callback is not None:
                    self._reconnect_callback()

        self._reconnect_task = self.hass.async_create_task(_reconnect())

    @callback
    def _set_available(self, available: bool) -> None:
        """Update shared session availability and signal entities."""
        if self.available == available:
            return
        self.available = available
        async_dispatcher_send(self.hass, self.signal)

    @callback
    def stop(self) -> None:
        """Cancel pending reconnect work."""
        if self._retry_handle is not None:
            self._retry_handle.cancel()
            self._retry_handle = None
        if self._reconnect_task is not None:
            self._reconnect_task.cancel()
            self._reconnect_task = None
        self._reconnect_callback = None

    async def stop_and_wait(self) -> None:
        """Cancel and await an in-flight login attempt."""
        task = self._reconnect_task
        self.stop()
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)
