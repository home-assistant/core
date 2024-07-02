"""Management of connection with an Onkyo Receiver."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import logging
from typing import Any

import pyeiscp
from pyeiscp import Connection as Receiver  # noqa: F401

from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)

ZONES = {"zone2": "Zone 2", "zone3": "Zone 3", "zone4": "Zone 4"}


@dataclass
class ReceiverInfo:
    """Onkyo Receiver information."""

    host: str
    port: int
    model_name: str
    identifier: str


async def async_interview(host: str) -> ReceiverInfo | None:
    """Interview Onkyo Receiver."""
    _LOGGER.debug("Interviewing receiver: %s", host)

    receiver_info: ReceiverInfo | None = None

    @callback
    async def _callback(conn: pyeiscp.Connection):
        """Receiver interviewed, connection not yet active."""
        nonlocal receiver_info
        info = ReceiverInfo(host, conn.port, conn.name, conn.identifier)
        _LOGGER.debug("Receiver interviewed: %s (%s)", info.model_name, info.host)
        receiver_info = info

    await pyeiscp.Connection.discover(
        host=host,
        discovery_callback=_callback,
    )

    return receiver_info


async def async_discover() -> Iterable[ReceiverInfo]:
    """Discover Onkyo Receivers."""
    _LOGGER.debug("Discovering receivers")

    receiver_infos: list[ReceiverInfo] = []

    @callback
    async def _callback(conn: pyeiscp.Connection):
        """Receiver discovered, connection not yet active."""
        info = ReceiverInfo(conn.host, conn.port, conn.name, conn.identifier)
        _LOGGER.debug("Receiver discovered: %s (%s)", info.model_name, info.host)
        receiver_infos.append(info)

    await pyeiscp.Connection.discover(discovery_callback=_callback)

    return receiver_infos


async def async_setup(
    info: ReceiverInfo,
    name: str | None,
    connect_callback: Callable[[Receiver], None],
    update_callback: Callable[[Receiver, tuple[str, str, Any]], None],
) -> Receiver:
    """Set up Onkyo Receiver."""

    receiver: Receiver | None = None

    @callback
    def _connect_callback(_origin: str) -> None:
        """Receiver (re)connected."""
        assert receiver is not None
        _LOGGER.debug("Receiver (re)connected: %s (%s)", receiver.name, receiver.host)

        # Discover what zones are available for the receiver by querying the power.
        # If we get a response for the specific zone, it means it is available.
        for zone in ZONES:
            receiver.query_property(zone, "power")

        connect_callback(receiver)

    @callback
    def _update_callback(message: tuple[str, str, Any], _origin: str) -> None:
        """Process new message from the receiver."""
        assert receiver is not None
        _LOGGER.debug("Received update callback from %s: %s", receiver.name, message)
        update_callback(receiver, message)

    _LOGGER.debug("Creating receiver: %s (%s)", info.model_name, info.host)
    receiver = await pyeiscp.Connection.create(
        host=info.host,
        port=info.port,
        connect_callback=_connect_callback,
        update_callback=_update_callback,
        auto_connect=False,
    )

    receiver.model_name = info.model_name
    receiver.identifier = info.identifier
    receiver.name = name or info.model_name

    return receiver
