"""client provides a ReliableClient for Philips Air Purifiers."""
from __future__ import annotations

import asyncio
from asyncio.tasks import FIRST_COMPLETED
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
import enum
import logging
from typing import Any

from aioairctrl import CoAPClient

_LOGGER = logging.getLogger(__name__)


@enum.unique
class Mode(enum.Enum):
    """
    Mode represents the purifier operation modes.

    The modes define how speed is controlled by the purifier itself. Only Sleep mode
    also turns off lights on the device.

    The values are the values exposed by the device's JSON API, for convenience when converting the JSON.
    """

    Manual = "M"
    Auto = "P"
    Allergen = "A"
    Sleep = "S"
    BacteriaVirus = "B"


@enum.unique
class FanSpeed(enum.Enum):
    """
    FanSpeed represents the different fan speeds reported by the device.

    The values are the values exposed by the device's JSON API, for convenience when converting the JSON.
    """

    Off = "0"
    Silent = "s"
    Speed1 = "1"
    Speed2 = "2"
    Speed3 = "3"
    Turbo = "t"


class Status:
    """Status represents the air purifier status in a form easily usable by the fan entity."""

    def __init__(
        self,
        device_id: str,
        name: str,
        model: str,
        firmware_version: str,
        wifi_firmware_version: str,
        is_on: bool,
        mode: Mode,
        fan_speed: FanSpeed,
    ) -> None:
        """
        Create a new status from the given attributes.

        The attributes are usually extracted from the JSON provided by the purifier.
        """
        self.device_id = device_id
        self.name = name
        self.model = model
        self.firmware_version = firmware_version
        self.wifi_firmware_version = wifi_firmware_version
        self.is_on = is_on
        self.mode = mode
        self.fan_speed = fan_speed

    def __repr__(self):
        """Return representation of the device status."""
        return (
            f"<Status device_id='{self.device_id}', name='{self.name}', model='{self.model}', "
            + f"firmware_version='{self.firmware_version}', "
            + f"wifi_firmware_version='{self.wifi_firmware_version}', "
            + f"is_on={self.is_on}, mode={self.mode}, fan_speed={self.fan_speed}>"
        )


class ReliableClient:
    """
    ReliableClient attempts to provide reliable communication with the Air Purifier.

    It does so by more or less aggressively timing out requests and retrying them.

    Note: Do NOT use multiple clients to connect from one machine to a single Air Purifier.
          Only one of the clients seems receive responses in this case.
    """

    def __init__(self, host: str, port: int) -> None:
        """Create a client. Does not connect yet."""
        self._host = host
        self._port = port
        self._background_task: asyncio.Task | None = None
        self._observe_task: asyncio.Task | None = None
        self._commmand_queue: asyncio.Queue = asyncio.Queue()
        # dict key is a unique id that can later be used to remove the observer.
        self._unavailable_callbacks = dict[int, Callable[[], None]]()
        self._status_callbacks = dict[int, Callable[[Status], None]]()
        self._last_status_at: datetime = datetime.now(timezone.utc)
        # The purifier sends a status update whenever something changes, which most commonly is the measured
        # pm25 value. When turned on, this usually happens every few seconds to every few 10s of seconds, depending
        # on how the amount of particles in the air changes.
        # When turned off, the updates usually only happen every 3 minutes.
        # 5 minutes should be enough to not time out when the purifier is turned off.
        self._status_timeout = timedelta(minutes=5)
        self._shutdown: asyncio.Future = asyncio.Future()

    def start(self) -> None:
        """
        Start the client, always trying to keep a connection open.

        If the client has been started before, nothing happens.
        """

        if self._background_task is not None:
            return

        self._background_task = asyncio.create_task(self._connection_loop())

    def stop(self):
        """Stop the client and close all open connections."""
        # Use cancel, so nothing breaks in case this is called multiple times.
        self._shutdown.cancel()

    async def _connection_loop(self) -> None:
        while True:
            _LOGGER.debug("connecting")

            # Notify all observers that the device is currently unavailable
            for callback in self._unavailable_callbacks.values():
                callback()

            try:
                client_create = CoAPClient.create(host=self._host, port=self._port)
                client = await asyncio.wait_for(client_create, timeout=10.0)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception(
                    "Unexpected exception while connecting, reattempting in 10s"
                )
                await asyncio.sleep(10.0)
                continue

            _LOGGER.debug("connected, starting status observations and command loop")

            # Reset status timeout
            self._last_status_at = datetime.now(timezone.utc)

            observe_task = asyncio.create_task(self._observe_status(client))
            status_watchdog = asyncio.create_task(self._status_watchdog())
            command_loop = asyncio.create_task(self._command_loop(client))
            await asyncio.wait(
                [command_loop, status_watchdog, self._shutdown],
                return_when=FIRST_COMPLETED,
            )

            # Connection is broken or shutdown was requested, so abort all tasks
            # (we only wait for the first to complete).
            observe_task.cancel()
            status_watchdog.cancel()
            command_loop.cancel()

            try:
                await client.shutdown()
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Client shutdown failed")

            if self._shutdown.cancelled():
                _LOGGER.debug("shutdown requested, stopping connection loop")
                return

    async def _observe_status(self, client: CoAPClient):
        async for json_status in client.observe_status():
            _LOGGER.debug("observed status: %s", repr(json_status))
            try:
                status = Status(
                    device_id=json_status["DeviceId"],
                    name=json_status["name"],
                    model=json_status["modelid"],
                    firmware_version=json_status["swversion"],
                    wifi_firmware_version=json_status["WifiVersion"],
                    is_on=(json_status["pwr"] == "1"),
                    mode=Mode(json_status["mode"]),
                    fan_speed=FanSpeed(json_status["om"]),
                )
            except KeyError:
                _LOGGER.exception("Failed to read status JSON")
                continue

            _LOGGER.debug("converted status: %s", repr(status))

            self._last_status_at = datetime.now(timezone.utc)
            for callback in self._status_callbacks.values():
                callback(status)

    async def _status_watchdog(self):
        while True:
            duration_until_timeout = (
                self._last_status_at + self._status_timeout
            ) - datetime.now(timezone.utc)

            if duration_until_timeout <= timedelta(0):
                _LOGGER.info("Status not received (timed out), reconnecting")
                # Timed out, return to reconnect.
                return

            await asyncio.sleep(duration_until_timeout.total_seconds())

    async def _command_loop(self, client: CoAPClient):
        # Empty command queue, so piled up commands don't all time out.
        while not self._commmand_queue.empty():
            _, result_future = await self._commmand_queue.get()
            result_future.set_result(None)

        while True:
            params, result_future = await self._commmand_queue.get()
            try:
                args, kwargs = params
                _LOGGER.debug(
                    "client set_control_values args: %s kwargs: %s",
                    repr(args),
                    repr(kwargs),
                )
                success = await client.set_control_values(*args, **kwargs)
                result_future.set_result(success)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Command failed, reconnecting")
                result_future.set_result(None)

                # Command failed, so the connection is probably broken.
                # Return to the connection loop for reconnecting.
                return

    async def _run_command(
        self,
        args: list[Any] = None,
        kwargs: dict[str, Any] = None,
    ) -> asyncio.Future[Any]:
        # pylint forces to not use [] and {} as default values, so we need this workaround.
        # disable=dangerous-default-value doesn't seem to work.
        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}

        result_future = asyncio.get_event_loop().create_future()
        await self._commmand_queue.put(((args, kwargs), result_future))
        return await result_future

    async def turn_on(self):
        """Turn the purifier on."""
        success = await self._run_command(kwargs={"data": {"pwr": "1"}})
        if not success:
            _LOGGER.error("Failed to turn on")

    async def turn_off(self):
        """Turn the purifier off."""
        success = await self._run_command(kwargs={"data": {"pwr": "0"}})
        if not success:
            _LOGGER.error("Failed to turn off")

    async def set_preset_mode(self, mode: Mode):
        """Activate a preset mode on the purifier."""
        success = await self._run_command(kwargs={"data": {"mode": mode.value}})
        if not success:
            _LOGGER.error("Failed to set preset_mode %s", mode)

    async def set_manual_speed(self, speed: FanSpeed):
        """Set the fan to a constant speed."""
        success = await self._run_command(kwargs={"data": {"om": speed.value}})
        if not success:
            _LOGGER.error("Failed to set manual speed %s", speed)

    def observe_status(self, id_: int, callback: Callable[[Status], None]) -> None:
        """Register the given callable to be called when the client reveives a status update from the purifier."""
        _LOGGER.debug("observing status")
        self._status_callbacks[id_] = callback

    def stop_observing_status(self, id_: int) -> None:
        """Unregister the callable previously registered with the given id from status updates."""
        _LOGGER.debug("stopped observing status")
        del self._status_callbacks[id_]

    def observe_unavailable(self, id_: int, callback: Callable[[], None]) -> None:
        """Register the given callable to be called when the client is disconnected from the purifier."""
        _LOGGER.debug("observing unavailable")
        self._unavailable_callbacks[id_] = callback

    def stop_observing_unavailable(self, id_: int) -> None:
        """Unregister the callable previously registered with the given id from unavailable updates."""
        _LOGGER.debug("stopped observing unavailable")
        del self._unavailable_callbacks[id_]
