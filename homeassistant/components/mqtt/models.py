"""Modesl used by multiple MQTT modules."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
import datetime as dt
from typing import TypedDict, Union

import attr

from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType

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


class MqttNotificationConfig(TypedDict, total=False):
    """Supply service parameters for MqttNotificationService."""

    command_topic: str
    command_template: Template
    encoding: str
    name: str
    qos: int
    retain: bool
    targets: list
    title: str
    device: ConfigType


class MqttTagConfig(TypedDict, total=False):
    """Supply service parameters for MQTTTagScanner."""

    topic: str
    value_template: Template
    device: ConfigType


MqttTypedDictConfigType = Union[MqttNotificationConfig, MqttTagConfig]
