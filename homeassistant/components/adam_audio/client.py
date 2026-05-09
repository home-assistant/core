"""Async-safe client wrapper around the AES70/OCA Device layer.

All blocking socket I/O runs in HA's executor thread pool so the event loop
is never blocked.  A single asyncio.Lock serialises all access so commands
and polls never interleave on the UDP socket.

State management
────────────────
• SET commands update ``self.state`` optimistically so the UI responds
  instantly without waiting for the next poll cycle.
• After each SET, a read-back verification confirms the device accepted the
  change.  If verification fails, the command is retried up to MAX_RETRIES
  times with RETRY_DELAY seconds between attempts.
• ``async_fetch_state()`` polls all 9 GET commands from the device and
  overwrites ``self.state`` with the real values.  This is called by the
  coordinator on every update interval.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import time
from typing import TYPE_CHECKING, Any

from pyadamaudiocontroller import Device

from homeassistant.exceptions import HomeAssistantError

from .const import LOGGER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@dataclass
class AdamAudioState:
    """Current device state."""

    mute: bool = False
    sleep: bool = False
    input_source: int = 1
    voicing: int = 0
    bass: int = 0
    desk: int = 0
    presence: int = 0
    treble: int = 0


class AdamAudioClient:
    """Manages one UDP connection to a single ADAM Audio A-Series device."""

    SOCKET_TIMEOUT: float = 10.0
    KEEPALIVE_TIMEOUT: int = 30
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 0.5  # seconds between retries

    def __init__(self, hass: HomeAssistant, host: str, port: int) -> None:
        """Initialize the client."""
        self._hass = hass
        self.host = host
        self.port = port
        self._device: Device | None = None
        self._lock = asyncio.Lock()
        self._last_keepalive: float = 0.0
        self.available: bool = False
        self.device_name: str = ""
        self.description: str = ""
        self.serial: str = ""
        self.state = AdamAudioState()

    async def async_setup(self) -> bool:
        """Connect to the device and fetch metadata."""
        return await self._hass.async_add_executor_job(self._setup)

    def _setup(self) -> bool:
        """Executor target for initial connection."""
        try:
            self._device = Device.from_address(self.host, self.port)
            self._device.set_timeout(self.SOCKET_TIMEOUT)
            self._device.send_keepalive()
            self._last_keepalive = time.monotonic()
            self.device_name = self._device.get_name()
            self.description = self._device.get_description()
            self.serial = self._device.get_serial_number()
            self.available = True
            LOGGER.info(
                "Connected to ADAM Audio '%s' at %s", self.description, self.host
            )
        except (OSError, TimeoutError, ValueError, RuntimeError) as err:
            LOGGER.warning("Cannot reach ADAM Audio device at %s — %s", self.host, err)
            self.available = False
            return False
        else:
            return True

    async def async_shutdown(self) -> None:
        """Release the UDP socket."""
        if self._device is not None:
            await self._hass.async_add_executor_job(self._device.close)

    async def async_fetch_state(self) -> bool:
        """Authoritative full state poll via sequential UDP requests."""
        async with self._lock:
            try:
                success = await self._hass.async_add_executor_job(
                    self._fetch_state_blocking
                )
                self.available = success
            except (OSError, TimeoutError, ValueError, RuntimeError) as err:
                LOGGER.debug(
                    "State fetch critical failure for %s: %s",
                    self.host,
                    err,
                    exc_info=True,
                )
                self.available = False
                return False
            else:
                return success

    def _fetch_state_blocking(self) -> bool:
        """Executor target for batched state polling."""
        if not self._device:
            return False

        self._device.drain()

        # Opportunistic keepalive
        try:
            now = time.monotonic()
            if self._last_keepalive == 0.0 or (
                now - self._last_keepalive > self.KEEPALIVE_TIMEOUT / 2
            ):
                self._device.send_keepalive(timeout_secs=5.0)
                self._last_keepalive = now
        except OSError:
            # Drain any late-arriving keepalive response so it doesn't
            # get read by the batch poll below.
            self._device.drain()

        try:
            responses = self._device.get_full_state_pdus()
            if not responses or len(responses) < 8:
                return False

            # Maps response indices to state attributes
            self.state.mute = responses[0].params[0].value == 5
            self.state.sleep = bool(responses[1].params[0].value)
            self.state.input_source = int(responses[2].params[0].value)
            self.state.voicing = int(responses[3].params[0].value)
            self.state.bass = int(responses[4].params[0].value)
            self.state.desk = int(responses[5].params[0].value)
            self.state.presence = int(responses[6].params[0].value)
            self.state.treble = int(responses[7].params[0].value)
        except (
            OSError,
            TimeoutError,
            ValueError,
            RuntimeError,
            IndexError,
            AttributeError,
            TypeError,
        ):
            LOGGER.warning("Batched poll failed for %s", self.host, exc_info=True)
            return False
        else:
            return True

    @property
    def _dev(self) -> Device:
        """Return the underlying device, raising if not connected."""
        if self._device is None:
            raise HomeAssistantError(f"Device at {self.host} is not connected")
        return self._device

    def _ensure_keepalive(self) -> None:
        """Send keepalive only if the session is truly stale (>30s)."""
        if self._device is None:
            return
        if time.monotonic() - self._last_keepalive > self.KEEPALIVE_TIMEOUT:
            try:
                self._device.send_keepalive(timeout_secs=1.0)
                self._last_keepalive = time.monotonic()
            except OSError:
                pass

    def _run_set(self, fn: Callable, *args: Any) -> None:
        """Executor target for SET commands."""
        self._ensure_keepalive()
        fn(*args)

    def _run_get(self, fn: Callable) -> Any:
        """Executor target for GET (verification) commands."""
        return fn()

    async def _async_send_with_retry(
        self,
        set_fn: Callable,
        set_args: tuple,
        get_fn: Callable,
        expected_value: Any,
    ) -> None:
        """Send a SET command and verify via GET read-back.

        Retries up to MAX_RETRIES times with RETRY_DELAY between attempts.
        The lock is acquired for each attempt (send + verify) then released
        between retries so polling isn't starved.
        """
        for attempt in range(1, self.MAX_RETRIES + 1):
            send_failed = False
            async with self._lock:
                # --- Send ---
                try:
                    await self._hass.async_add_executor_job(
                        self._run_set, set_fn, *set_args
                    )
                    self.available = True
                except OSError as err:
                    self.available = False
                    if attempt == self.MAX_RETRIES:
                        LOGGER.info(
                            "Command %s failed after %d attempts on %s: %s",
                            set_fn.__name__,
                            self.MAX_RETRIES,
                            self.host,
                            err,
                        )
                        raise HomeAssistantError(
                            f"Command {set_fn.__name__} failed after "
                            f"{self.MAX_RETRIES} attempts: {err}"
                        ) from err
                    send_failed = True

                if not send_failed:
                    # --- Verify ---
                    try:
                        actual = await self._hass.async_add_executor_job(
                            self._run_get, get_fn
                        )
                        if actual == expected_value:
                            return  # ✓ Verified
                        LOGGER.debug(
                            "Verify mismatch for %s: expected %s, got %s "
                            "(attempt %d/%d)",
                            set_fn.__name__,
                            expected_value,
                            actual,
                            attempt,
                            self.MAX_RETRIES,
                        )
                    except OSError, TimeoutError, ValueError, RuntimeError:
                        LOGGER.debug(
                            "Verify read failed for %s (attempt %d/%d)",
                            set_fn.__name__,
                            attempt,
                            self.MAX_RETRIES,
                        )

            # Retry after releasing the lock
            if attempt < self.MAX_RETRIES:
                await asyncio.sleep(self.RETRY_DELAY)

        LOGGER.info(
            "Command %s failed after %d attempts on %s (verification never matched)",
            set_fn.__name__,
            self.MAX_RETRIES,
            self.host,
        )

    # ── Legacy send (for commands without GET verification) ────────────────

    async def _async_send(self, fn: Callable, *args: Any) -> None:
        """Send a single SET command (no verification)."""
        async with self._lock:
            try:
                await self._hass.async_add_executor_job(self._run_set, fn, *args)
                self.available = True
            except OSError as err:
                self.available = False
                LOGGER.error("Command to %s failed: %s", self.host, err)
                raise HomeAssistantError(
                    f"Command to {self.host} failed: {err}"
                ) from err

    # ── Public SET API ───────────────────────────────────────────────────────

    async def async_set_mute(self, value: bool) -> None:
        """Set the mute state."""
        await self._async_send_with_retry(
            self._dev.set_mute,
            (value,),
            self._dev.get_mute,
            value,
        )
        self.state.mute = value

    async def async_set_sleep(self, value: bool) -> None:
        """Set the sleep/standby state."""
        await self._async_send_with_retry(
            self._dev.set_sleep,
            (value,),
            self._dev.get_sleep,
            value,
        )
        self.state.sleep = value

    async def async_set_input(self, value: int) -> None:
        """Set the input source."""
        await self._async_send_with_retry(
            self._dev.set_input,
            (value,),
            self._dev.get_input,
            value,
        )
        self.state.input_source = value

    async def async_set_voicing(self, value: int) -> None:
        """Set the voicing mode."""
        await self._async_send_with_retry(
            self._dev.set_voicing,
            (value,),
            self._dev.get_voicing,
            value,
        )
        self.state.voicing = value

    async def async_set_bass(self, value: int) -> None:
        """Set the bass EQ level."""
        await self._async_send_with_retry(
            self._dev.set_bass,
            (value,),
            self._dev.get_bass,
            value,
        )
        self.state.bass = value

    async def async_set_desk(self, value: int) -> None:
        """Set the desk EQ level."""
        await self._async_send_with_retry(
            self._dev.set_desk,
            (value,),
            self._dev.get_desk,
            value,
        )
        self.state.desk = value

    async def async_set_presence(self, value: int) -> None:
        """Set the presence EQ level."""
        await self._async_send_with_retry(
            self._dev.set_presence,
            (value,),
            self._dev.get_presence,
            value,
        )
        self.state.presence = value

    async def async_set_treble(self, value: int) -> None:
        """Set the treble EQ level."""
        await self._async_send_with_retry(
            self._dev.set_treble,
            (value,),
            self._dev.get_treble,
            value,
        )
        self.state.treble = value
