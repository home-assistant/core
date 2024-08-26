"""Onkyo receiver."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
import contextlib
from dataclasses import dataclass
import logging

import pyeiscp

from .const import DEVICE_DISCOVERY_TIMEOUT, DEVICE_INTERVIEW_TIMEOUT

_LOGGER = logging.getLogger(__name__)


@dataclass
class Receiver:
    """Onkyo receiver."""

    conn: pyeiscp.Connection
    model_name: str
    identifier: str
    name: str
    discovered: bool


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
