"""Flic device protocol handlers.

This module provides device-specific protocol handlers for Flic devices:
- Flic2ProtocolHandler: For standard Flic 2 buttons
- DuoProtocolHandler: For Flic Duo buttons (two buttons, rotation, gestures)
- TwistProtocolHandler: For Flic Twist buttons (rotation, selector modes)
"""

from __future__ import annotations

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
    serial_number: str | None = None,
    push_twist_mode: PushTwistMode = PushTwistMode.DEFAULT,
) -> DeviceProtocolHandler:
    """Create the appropriate protocol handler for a device type.

    Args:
        device_type: The type of Flic device
        serial_number: Optional serial number (used for detection if device_type is None)
        push_twist_mode: Push twist mode setting for Twist devices

    Returns:
        A protocol handler instance for the device type

    """
    # If device type is explicitly specified, use it
    match device_type:
        case DeviceType.TWIST:
            return TwistProtocolHandler(push_twist_mode=push_twist_mode)
        case DeviceType.DUO:
            return DuoProtocolHandler()
        case DeviceType.FLIC2:
            return Flic2ProtocolHandler()

    # Fallback: Try to detect from serial number prefix
    if serial_number:
        return create_handler(
            DeviceType.from_serial_number(serial_number),
            push_twist_mode=push_twist_mode,
        )

    # Default to Flic 2
    return Flic2ProtocolHandler()
