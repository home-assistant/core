"""Connection handling for the roomba integration.

Many robots stay awake, with the status light on, for as long as a local MQTT
session is open. Unless continuous mode is enabled, the robot is polled
instead: connect, collect telemetry, disconnect. The session stays open while
the robot is on a mission and for a short while after a command.

With polling disabled in the entry's system options, the robot is only
refreshed on request, e.g. by a user automation calling
``homeassistant.update_entity`` on its own schedule.
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime
import logging
import time

from roombapy import RoombaClient

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later, async_track_time_interval

from .const import (
    ACTIVE_PHASES,
    COMMAND_HOLD_SECONDS,
    PERIODIC_UPDATE_INTERVAL,
    TELEMETRY_SETTLE_SECONDS,
)

_LOGGER = logging.getLogger(__name__)

type SessionCallable = Callable[[HomeAssistant, RoombaClient], Awaitable[object]]


class RoombaConnection:
    """Keep the robot connected, either permanently or on demand."""

    def __init__(
        self,
        hass: HomeAssistant,
        roomba: RoombaClient,
        *,
        continuous: bool,
        polling: bool,
        connect: SessionCallable,
        disconnect: SessionCallable,
    ) -> None:
        """Initialize the connection handler."""
        self.hass = hass
        self.roomba = roomba
        self.continuous = continuous
        self.polling = polling
        self._connect = connect
        self._disconnect = disconnect
        self._lock = asyncio.Lock()
        self._hold_until = 0.0
        self._unsub_interval: CALLBACK_TYPE | None = None
        self._unsub_release: CALLBACK_TYPE | None = None
        self._closed = False

    @property
    def robot_active(self) -> bool:
        """Return True while the robot is on a mission."""
        reported = self.roomba.master_state.get("state", {}).get("reported", {})
        phase = reported.get("cleanMissionStatus", {}).get("phase")
        return phase in ACTIVE_PHASES

    @callback
    def async_start(self) -> None:
        """Start polling; the robot is already connected at this point."""
        if self.continuous:
            return
        if self.polling:
            self._unsub_interval = async_track_time_interval(
                self.hass, self._async_poll, PERIODIC_UPDATE_INTERVAL
            )
        self._schedule_release(TELEMETRY_SETTLE_SECONDS)

    async def async_stop(self) -> None:
        """Stop polling and close the session."""
        self._closed = True
        if self._unsub_interval:
            self._unsub_interval()
            self._unsub_interval = None
        self._cancel_release()
        async with self._lock:
            await self._disconnect(self.hass, self.roomba)

    async def async_ensure_connected(self) -> None:
        """Open a session, if needed, before a command is sent."""
        if self.continuous:
            return
        self._hold_until = time.monotonic() + COMMAND_HOLD_SECONDS
        async with self._lock:
            if not self.roomba.connected:
                _LOGGER.debug("Connecting to send a command")
                await self._connect(self.hass, self.roomba)
        self._schedule_release(COMMAND_HOLD_SECONDS)

    async def _async_poll(self, _now: datetime) -> None:
        await self.async_refresh()

    async def async_refresh(self) -> None:
        """Refresh the state with a short-lived session."""
        if self.continuous:
            return
        async with self._lock:
            if self._closed or self._unsub_release:
                # Already collecting telemetry or holding after a command.
                return
            if self.roomba.connected:
                connected_now = False
            else:
                _LOGGER.debug("Refreshing state: connecting")
                try:
                    await self._connect(self.hass, self.roomba)
                except HomeAssistantError as err:
                    _LOGGER.debug("Refresh failed, retrying later: %s", err)
                    return
                connected_now = True
        if connected_now:
            # Give the robot time to publish its full state.
            self._schedule_release(TELEMETRY_SETTLE_SECONDS)
        else:
            await self._async_release()

    @callback
    def _schedule_release(self, delay: float) -> None:
        """Release the session after a delay, replacing a pending release."""
        self._cancel_release()

        async def _release(_now: datetime) -> None:
            self._unsub_release = None
            await self._async_release()

        self._unsub_release = async_call_later(self.hass, delay, _release)

    @callback
    def _cancel_release(self) -> None:
        if self._unsub_release:
            self._unsub_release()
            self._unsub_release = None

    async def _async_release(self) -> None:
        """Disconnect unless the session is still needed."""
        async with self._lock:
            if (
                self._closed
                or not self.roomba.connected
                or time.monotonic() < self._hold_until
            ):
                return
            if self.robot_active:
                _LOGGER.debug("Robot on a mission, keeping the session open")
                return
            _LOGGER.debug("Robot idle, closing the session so it can sleep")
            await self._disconnect(self.hass, self.roomba)
