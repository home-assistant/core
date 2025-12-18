"""Tests for the Sunricher Sunricher DALI integration."""

from collections.abc import Callable
from unittest.mock import MagicMock

from PySrDaliGateway import CallbackEventType


def find_device_listener(
    device: MagicMock, event_type: CallbackEventType
) -> Callable[..., None]:
    """Find the registered listener callback for a specific device and event type."""
    for call in device.register_listener.call_args_list:
        if call[0][0] == event_type:
            return call[0][1]
    raise AssertionError(
        f"Listener for event type {event_type} not found on device {device.dev_id}"
    )
