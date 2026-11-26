"""Connection handling for the roomba integration.

Many robots stay awake, with the status light on, for as long as a local MQTT
session is open. Unless continuous mode is enabled, the robot is polled
instead: connect, collect telemetry, disconnect. The session stays open while
the robot is on a mission and for a short while after a command.

Robots answer at very different speeds depending on model and firmware, so
instead of a fixed delay the session is released once the robot has gone
quiet after publishing its state, with an upper bound.

With polling disabled in the entry's system options, the robot is only
refreshed on request, e.g. by a user automation calling
``homeassistant.update_entity`` on its own schedule.
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
import logging
import time

from roombapy import RoombaClient, RoombaMessage

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later, async_track_time_interval

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PERIODIC_UPDATE_INTERVAL = timedelta(minutes=5)
# 900-series robots on 2.x firmware publish their state in many messages over
# several seconds, newer ones in a single message.
TELEMETRY_QUIET_SECONDS = 2
TELEMETRY_MAX_SECONDS = 30
COMMAND_HOLD_SECONDS = 120
MISSION_CHECK_SECONDS = 60
ACTIVE_PHASES = frozenset({"run", "hmMidMsn", "hmPostMsn", "hmUsrDock", "evac"})
MISSION_FIELDS = frozenset({"phase", "cycle"})

type SessionCallable = Callable[[HomeAssistant, RoombaClient], Awaitable[object]]


class RoombaConnection:
    """Keep the robot connected, either permanently or on demand."""

    def __init__(
        self,
        hass: HomeAssistant,
        roomba: RoombaClient,
        host: str,
        *,
        continuous: bool,
        polling: bool,
        connect: SessionCallable,
        disconnect: SessionCallable,
    ) -> None:
        """Initialize the connection handler."""
        self.hass = hass
        self.roomba = roomba
        self.host = host
        self.continuous = continuous
        self.polling = polling
        self._connect = connect
        self._disconnect = disconnect
        self._lock = asyncio.Lock()
        self._hold_until = 0.0
        self._unsub_interval: CALLBACK_TYPE | None = None
        self._unsub_settle: CALLBACK_TYPE | None = None
        self._unsub_release: CALLBACK_TYPE | None = None
        self._unsub_message: CALLBACK_TYPE | None = None
        self._unsub_state: CALLBACK_TYPE | None = None
        self._session_start = 0.0
        self._last_message: float | None = None
        self._mission_fields: set[str] = set()
        self._opening = False
        self._fresh = asyncio.Event()
        self._closed = False
        self._unreachable = False

    @property
    def robot_active(self) -> bool:
        """Return True while the robot is on a mission."""
        reported = self.roomba.master_state.get("state", {}).get("reported", {})
        status = reported.get("cleanMissionStatus", {})
        phase = status.get("phase")
        if phase in ACTIVE_PHASES:
            return True
        # Recharging on the dock in the middle of a mission.
        return phase == "charge" and status.get("cycle") not in (None, "none")

    @callback
    def async_start(self) -> None:
        """Start polling; the robot is already connected at this point."""
        if self.continuous:
            return
        self._unsub_message = self.roomba.register_on_message_callback(self._on_message)
        self._unsub_state = self.roomba.register_on_connection_state_callback(
            self._on_connection_state
        )
        if self.polling:
            self._unsub_interval = async_track_time_interval(
                self.hass, self._async_poll, PERIODIC_UPDATE_INTERVAL
            )
        # Setup collected the first state, which may still be partial.
        self._session_start = self._last_message = time.monotonic()
        reported = self.roomba.master_state.get("state", {}).get("reported", {})
        mission = reported.get("cleanMissionStatus") or {}
        self._mission_fields.update(MISSION_FIELDS.intersection(mission))
        self._schedule_settle()

    async def async_stop(self) -> None:
        """Stop polling and close the session."""
        self._closed = True
        if self._unsub_interval:
            self._unsub_interval()
            self._unsub_interval = None
        # After an operation in flight, which may still schedule timers.
        async with self._lock:
            self._cancel_settle()
            self._cancel_release()
            if self._unsub_message:
                self._unsub_message()
                self._unsub_message = None
            if self._unsub_state:
                self._unsub_state()
                self._unsub_state = None
            # Do not leave anyone waiting for state that will not come.
            self._fresh.set()
            await self._disconnect(self.hass, self.roomba)

    @callback
    def _on_message(self, message: RoombaMessage) -> None:
        """Note when the robot last published something other than Wi-Fi stats."""
        reported = (message.get("state") or {}).get("reported") or {}
        if len(reported) > 1 or (reported and "signal" not in reported):
            self._last_message = time.monotonic()
        mission = reported.get("cleanMissionStatus") or {}
        self._mission_fields.update(MISSION_FIELDS.intersection(mission))

    @property
    def _mission_fresh(self) -> bool:
        """Return True once this session has reported the mission state."""
        return self._mission_fields >= MISSION_FIELDS

    @callback
    def _on_connection_state(self, state: str, _error: str | None) -> None:
        """Track sessions that the client drops and recovers on its own."""
        if state == "disconnected":
            self._mission_fields.clear()
        elif not self._opening and not self._closed:
            # Collect the recovered session's state before trusting it.
            self._fresh.clear()
            self._last_message = None
            self._session_start = time.monotonic()
            self._schedule_settle()

    async def async_ensure_connected(self, *, wait: bool = False) -> None:
        """Open a session if needed before a command.

        With ``wait``, also wait for fresh state, for commands that depend on
        the current mission state.
        """
        if self.continuous:
            return
        async with self._lock:
            if self._closed:
                return
            if not self.roomba.connected:
                _LOGGER.debug("Connecting to send a command")
                await self._async_open()
                self._mark_reachable()
            self._hold_until = time.monotonic() + COMMAND_HOLD_SECONDS
            self._schedule_release(COMMAND_HOLD_SECONDS)
        if wait:
            await self._async_wait_fresh()
            if not self._mission_fresh:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="no_mission_state"
                )

    async def async_refresh(self, *, wait: bool = False) -> None:
        """Refresh the state with a short-lived session.

        With ``wait``, return only once the robot has published its state, so
        that a caller such as ``homeassistant.update_entity`` sees fresh data.
        """
        if self.continuous:
            return
        async with self._lock:
            if self._closed:
                return
            if self.roomba.connected:
                check_release = not self._unsub_settle
            else:
                _LOGGER.debug("Refreshing state: connecting")
                try:
                    await self._async_open()
                except HomeAssistantError as err:
                    if not self._unreachable:
                        self._unreachable = True
                        _LOGGER.info(
                            "Roomba at %s is unreachable, showing its last known"
                            " state until it responds again. It accepts one local"
                            " connection at a time, so another client such as the"
                            " iRobot app on the home network can also block it: %s",
                            self.host,
                            err,
                        )
                    return
                self._mark_reachable()
                check_release = False
        if check_release:
            await self._async_release()
        if wait:
            await self._async_wait_fresh()

    async def _async_poll(self, _now: datetime) -> None:
        await self.async_refresh()

    async def _async_open(self) -> None:
        """Open a session; the caller holds the lock."""
        # A settle timer from a dropped session must not mark this one fresh.
        self._cancel_settle()
        # A dropped session may still be reconnecting in the background, and
        # the client refuses to connect again until it is torn down.
        await self._disconnect(self.hass, self.roomba)
        self._fresh.clear()
        self._last_message = None
        self._mission_fields.clear()
        self._opening = True
        try:
            await self._connect(self.hass, self.roomba)
        finally:
            self._opening = False
        self._session_start = time.monotonic()
        self._schedule_settle()

    async def _async_wait_fresh(self) -> None:
        """Wait until the current session has collected the robot's state."""
        if self._fresh.is_set():
            return
        try:
            async with asyncio.timeout(TELEMETRY_MAX_SECONDS + 1):
                await self._fresh.wait()
        except TimeoutError:
            _LOGGER.debug("Timed out waiting for state from %s", self.host)

    @callback
    def _mark_reachable(self) -> None:
        if self._unreachable:
            self._unreachable = False
            _LOGGER.info("Roomba at %s is reachable again", self.host)

    @callback
    def _schedule_settle(self) -> None:
        """Mark the state fresh once the robot has finished publishing."""
        self._cancel_settle()

        async def _check(_now: datetime) -> None:
            self._unsub_settle = None
            if self._telemetry_wait() > 0:
                self._schedule_settle()
                return
            if self._last_message is None:
                _LOGGER.debug("No state received within %s s", TELEMETRY_MAX_SECONDS)
            self._fresh.set()
            await self._async_release()

        self._unsub_settle = async_call_later(self.hass, self._telemetry_wait(), _check)

    @callback
    def _cancel_settle(self) -> None:
        if self._unsub_settle:
            self._unsub_settle()
            self._unsub_settle = None

    def _telemetry_wait(self) -> float:
        """Return how much longer to wait for the robot to go quiet."""
        now = time.monotonic()
        remaining = self._session_start + TELEMETRY_MAX_SECONDS - now
        if remaining <= 0:
            return 0
        if self._last_message is None:
            return min(TELEMETRY_QUIET_SECONDS, remaining)
        quiet_left = self._last_message + TELEMETRY_QUIET_SECONDS - now
        return min(max(quiet_left, 0), remaining)

    @callback
    def _schedule_release(self, delay: float) -> None:
        """Check whether to release the session after a delay."""
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
        """Disconnect unless the session is still needed.

        Every reason to keep the session schedules another check, so it is
        released even with polling disabled.
        """
        async with self._lock:
            if self._closed or self._unsub_settle:
                return
            if (hold_left := self._hold_until - time.monotonic()) > 0:
                self._schedule_release(hold_left)
                return
            # A mission phase cached from an earlier session must not pin it.
            if self._mission_fresh and self.robot_active:
                _LOGGER.debug("Robot on a mission, keeping the session open")
                self._schedule_release(MISSION_CHECK_SECONDS)
                return
            self._cancel_release()
            # A dropped session is torn down too, so it stops reconnecting.
            _LOGGER.debug("Robot idle, closing the session so it can sleep")
            await self._disconnect(self.hass, self.roomba)
