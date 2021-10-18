"""Modesl used by multiple MQTT modules."""
from __future__ import annotations

import datetime as dt
from typing import Awaitable, Callable, Union

import attr

PublishPayloadType = Union[str, bytes, int, float, None]
ReceivePayloadType = Union[str, bytes]


@attr.s(slots=True, frozen=True)
class PublishMessage:
    """MQTT Message."""

    topic: str = attr.ib()
    payload: PublishPayloadType = attr.ib()
    qos: int = attr.ib()
    retain: bool = attr.ib()


@attr.s(slots=True, frozen=True)
class ReceiveMessage:
    """MQTT Message."""

    topic: str = attr.ib()
    payload: ReceivePayloadType = attr.ib()
    qos: int = attr.ib()
    retain: bool = attr.ib()
    subscribed_topic: str = attr.ib(default=None)
    timestamp: dt.datetime = attr.ib(default=None)


AsyncMessageCallbackType = Callable[[ReceiveMessage], Awaitable[None]]
MessageCallbackType = Callable[[ReceiveMessage], None]
