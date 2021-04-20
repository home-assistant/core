"""Modesl used by multiple MQTT modules."""
from __future__ import annotations

import datetime as dt
from typing import Callable, Union

import attr

PublishPayloadType = Union[str, bytes, int, float, None]


@attr.s(slots=True, frozen=True)
class Message:
    """MQTT Message."""

    topic: str = attr.ib()
    payload: PublishPayloadType = attr.ib()
    qos: int = attr.ib()
    retain: bool = attr.ib()
    subscribed_topic: str | None = attr.ib(default=None)
    timestamp: dt.datetime | None = attr.ib(default=None)


MessageCallbackType = Callable[[Message], None]
