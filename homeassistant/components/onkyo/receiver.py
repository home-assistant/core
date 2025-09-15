"""Onkyo receiver."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
import contextlib
from dataclasses import dataclass, field
import logging
from typing import TYPE_CHECKING

import aioonkyo
from aioonkyo import Instruction, Receiver, ReceiverInfo, Status, connect, query

from homeassistant.components import network
from homeassistant.core import HomeAssistant

from .const import DEVICE_DISCOVERY_TIMEOUT, DEVICE_INTERVIEW_TIMEOUT, ZONES

if TYPE_CHECKING:
    from . import OnkyoConfigEntry

_LOGGER = logging.getLogger(__name__)


@dataclass
class Callbacks:
    """Receiver callbacks."""

    connect: list[Callable[[bool], Awaitable[None]]] = field(default_factory=list)
    update: list[Callable[[Status], Awaitable[None]]] = field(default_factory=list)

    def clear(self) -> None:
        """Clear all callbacks."""
        self.connect.clear()
        self.update.clear()


class ReceiverManager:
    """Receiver manager."""

    hass: HomeAssistant
    entry: OnkyoConfigEntry
    info: ReceiverInfo
    receiver: Receiver | None = None
    callbacks: Callbacks

    _started: asyncio.Event

    def __init__(
        self, hass: HomeAssistant, entry: OnkyoConfigEntry, info: ReceiverInfo
    ) -> None:
        """Init receiver manager."""
        self.hass = hass
        self.entry = entry
        self.info = info
        self.callbacks = Callbacks()
        self._started = asyncio.Event()

    async def start(self) -> Awaitable[None] | None:
        """Start the receiver manager run.

        Returns `None`, if everything went fine.
        Returns an awaitable with exception set, if something went wrong.
        """
        manager_task = self.entry.async_create_background_task(
            self.hass, self._run(), "run_connection"
        )
        wait_for_started_task = asyncio.create_task(self._started.wait())
        done, _ = await asyncio.wait(
            (manager_task, wait_for_started_task), return_when=asyncio.FIRST_COMPLETED
        )
        if manager_task in done:
            # Something went wrong, so let's return the manager task,
            # so that it can be awaited to error out
            return manager_task

        return None

    async def _run(self) -> None:
        """Run the connection to the receiver."""
        reconnect = False
        while True:
            try:
                async with connect(self.info, retry=reconnect) as self.receiver:
                    if not reconnect:
                        self._started.set()
                    else:
                        _LOGGER.info("Reconnected: %s", self.info)

                    await self.on_connect(reconnect=reconnect)

                    while message := await self.receiver.read():
                        await self.on_update(message)

                reconnect = True

            finally:
                _LOGGER.info("Disconnected: %s", self.info)

    async def on_connect(self, reconnect: bool) -> None:
        """Receiver (re)connected."""

        # Discover what zones are available for the receiver by querying the power.
        # If we get a response for the specific zone, it means it is available.
        for zone in ZONES:
            await self.write(query.Power(zone))

        for callback in self.callbacks.connect:
            await callback(reconnect)

    async def on_update(self, message: Status) -> None:
        """Process new message from the receiver."""
        for callback in self.callbacks.update:
            await callback(message)

    async def write(self, message: Instruction) -> None:
        """Write message to the receiver."""
        assert self.receiver is not None
        await self.receiver.write(message)

    def start_unloading(self) -> None:
        """Start unloading."""
        self.callbacks.clear()


async def async_interview(host: str) -> ReceiverInfo | None:
    """Interview the receiver."""
    info: ReceiverInfo | None = None
    with contextlib.suppress(asyncio.TimeoutError):
        async with asyncio.timeout(DEVICE_INTERVIEW_TIMEOUT):
            info = await aioonkyo.interview(host)
    return info


async def async_discover(hass: HomeAssistant) -> Iterable[ReceiverInfo]:
    """Discover receivers."""
    all_infos: dict[str, ReceiverInfo] = {}

    async def collect_infos(address: str) -> None:
        with contextlib.suppress(asyncio.TimeoutError):
            async with asyncio.timeout(DEVICE_DISCOVERY_TIMEOUT):
                async for info in aioonkyo.discover(address):
                    all_infos.setdefault(info.identifier, info)

    broadcast_addrs = await network.async_get_ipv4_broadcast_addresses(hass)
    tasks = [collect_infos(str(address)) for address in broadcast_addrs]

    await asyncio.gather(*tasks)

    return all_infos.values()
