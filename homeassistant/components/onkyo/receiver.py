"""Onkyo receiver."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
import contextlib
from dataclasses import dataclass, field
import logging
from typing import Any

import pyeiscp

from .const import DEVICE_DISCOVERY_TIMEOUT, DEVICE_INTERVIEW_TIMEOUT, ZONES

_LOGGER = logging.getLogger(__name__)


@dataclass
class Callbacks:
    """Onkyo Receiver Callbacks."""

    connect: list[Callable[[Receiver], None]] = field(default_factory=list)
    update: list[Callable[[Receiver, tuple[str, str, Any]], None]] = field(
        default_factory=list
    )


@dataclass
class Receiver:
    """Onkyo receiver."""

    conn: pyeiscp.Connection
    model_name: str
    identifier: str
    host: str
    first_connect: bool = True
    callbacks: Callbacks = field(default_factory=Callbacks)

    @classmethod
    async def async_create(cls, info: ReceiverInfo) -> Receiver:
        """Set up Onkyo Receiver."""

        receiver: Receiver | None = None

        def on_connect(_origin: str) -> None:
            assert receiver is not None
            receiver.on_connect()

        def on_update(message: tuple[str, str, Any], _origin: str) -> None:
            assert receiver is not None
            receiver.on_update(message)

        _LOGGER.debug("Creating receiver: %s (%s)", info.model_name, info.host)

        connection = await pyeiscp.Connection.create(
            host=info.host,
            port=info.port,
            connect_callback=on_connect,
            update_callback=on_update,
            auto_connect=False,
        )

        return (
            receiver := cls(
                conn=connection,
                model_name=info.model_name,
                identifier=info.identifier,
                host=info.host,
            )
        )

    def on_connect(self) -> None:
        """Receiver (re)connected."""
        _LOGGER.debug("Receiver (re)connected: %s (%s)", self.model_name, self.host)

        # Discover what zones are available for the receiver by querying the power.
        # If we get a response for the specific zone, it means it is available.
        for zone in ZONES:
            self.conn.query_property(zone, "power")

        for callback in self.callbacks.connect:
            callback(self)

        self.first_connect = False

    def on_update(self, message: tuple[str, str, Any]) -> None:
        """Process new message from the receiver."""
        _LOGGER.debug("Received update callback from %s: %s", self.model_name, message)
        for callback in self.callbacks.update:
            callback(self, message)


@dataclass
class ReceiverInfo:
    """Onkyo receiver information."""

    host: str
    port: int
    model_name: str
    identifier: str


async def async_interview(host: str) -> ReceiverInfo | None:
    """Interview Onkyo Receiver."""
    _LOGGER.debug("Interviewing receiver: %s", host)

    receiver_info: ReceiverInfo | None = None

    event = asyncio.Event()

    async def _callback(conn: pyeiscp.Connection) -> None:
        """Receiver interviewed, connection not yet active."""
        nonlocal receiver_info
        if receiver_info is None:
            info = ReceiverInfo(host, conn.port, conn.name, conn.identifier)
            _LOGGER.debug("Receiver interviewed: %s (%s)", info.model_name, info.host)
            receiver_info = info
            event.set()

    timeout = DEVICE_INTERVIEW_TIMEOUT

    await pyeiscp.Connection.discover(
        host=host, discovery_callback=_callback, timeout=timeout
    )

    with contextlib.suppress(asyncio.TimeoutError):
        await asyncio.wait_for(event.wait(), timeout)

    return receiver_info


async def async_discover() -> Iterable[ReceiverInfo]:
    """Discover Onkyo Receivers."""
    _LOGGER.debug("Discovering receivers")

    receiver_infos: list[ReceiverInfo] = []

    async def _callback(conn: pyeiscp.Connection) -> None:
        """Receiver discovered, connection not yet active."""
        info = ReceiverInfo(conn.host, conn.port, conn.name, conn.identifier)
        _LOGGER.debug("Receiver discovered: %s (%s)", info.model_name, info.host)
        receiver_infos.append(info)

    timeout = DEVICE_DISCOVERY_TIMEOUT

    await pyeiscp.Connection.discover(discovery_callback=_callback, timeout=timeout)

    await asyncio.sleep(timeout)

    return receiver_infos
