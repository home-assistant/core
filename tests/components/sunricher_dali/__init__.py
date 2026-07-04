"""Tests for the Sunricher Sunricher DALI integration."""

from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

from PySrDaliGateway import CallbackEventType


def find_device_listener(
    device: MagicMock, event_type: CallbackEventType
) -> Callable[..., None]:
    """Find the registered listener callback for a specific device and event type.

    Returns a wrapper that calls all registered listeners for the event type.
    """
    callbacks: list[Callable[..., None]] = [
        call[0][1]
        for call in device.register_listener.call_args_list
        if call[0][0] == event_type
    ]

    if not callbacks:
        raise AssertionError(
            f"Listener for event type {event_type} not found on device {device.dev_id}"
        )

    def trigger_all(*args: Any, **kwargs: Any) -> None:
        for cb in callbacks:
            cb(*args, **kwargs)

    return trigger_all


def trigger_availability_callback(device: MagicMock, available: bool) -> None:
    """Trigger availability callbacks registered on the device mock."""
    callback = find_device_listener(device, CallbackEventType.ONLINE_STATUS)
    callback(available)
