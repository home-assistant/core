"""Tests for the System Nexa 2 component."""

from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock

import pytest
from sn2.device import UpdateEvent


def find_update_callback(
    mock: MagicMock,
) -> Callable[[UpdateEvent], Awaitable[None]]:
    """Find the update callback that was registered with the device."""
    for call in mock.initiate_device.call_args_list:
        if call.kwargs.get("on_update"):
            return call.kwargs["on_update"]
    pytest.fail("Update callback not found in mock calls")
