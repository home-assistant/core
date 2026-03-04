"""Flic device protocol handlers."""

from __future__ import annotations

from typing import assert_never

from ..const import DeviceType, PushTwistMode
from .base import ButtonEvent, DeviceCapabilities, DeviceProtocolHandler, RotateEvent
from .duo import DuoProtocolHandler
from .flic2 import Flic2ProtocolHandler
from .twist import TwistProtocolHandler

__all__ = [
    "ButtonEvent",
    "DeviceCapabilities",
    "DeviceProtocolHandler",
    "DuoProtocolHandler",
    "Flic2ProtocolHandler",
    "RotateEvent",
    "TwistProtocolHandler",
    "create_handler",
]


def create_handler(
    device_type: DeviceType,
    push_twist_mode: PushTwistMode = PushTwistMode.DEFAULT,
) -> DeviceProtocolHandler:
    """Create the appropriate protocol handler for a device type."""
    match device_type:
        case DeviceType.TWIST:
            return TwistProtocolHandler(push_twist_mode=push_twist_mode)
        case DeviceType.DUO:
            return DuoProtocolHandler()
        case DeviceType.FLIC2:
            return Flic2ProtocolHandler()
        case _:
            assert_never(device_type)
