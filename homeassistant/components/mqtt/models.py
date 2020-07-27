"""Modesl used by multiple MQTT modules."""
import datetime as dt
from typing import Callable, Optional, Union

import attr

PublishPayloadType = Union[str, bytes, int, float, None]


@attr.s(slots=True, frozen=True)
class Message:
    """MQTT Message."""

    topic: str = attr.ib()
    payload: PublishPayloadType = attr.ib()
    qos: int = attr.ib()
    retain: bool = attr.ib()
    subscribed_topic: Optional[str] = attr.ib(default=None)
    timestamp: Optional[dt.datetime] = attr.ib(default=None)


MessageCallbackType = Callable[[Message], None]
