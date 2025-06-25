"""Tests for the SMLIGHT Zigbee adapter integration."""

from collections.abc import Callable
from unittest.mock import MagicMock

from pysmlight.const import Events as SmEvents
from pysmlight.sse import MessageEvent


def get_mock_event_function(
    mock: MagicMock, event: SmEvents
) -> Callable[[MessageEvent], None]:
    """Extract event function from mock call_args."""
    return next(
        (
            call_args[0][1]
            for call_args in mock.sse.register_callback.call_args_list
            if call_args[0][0] == event
        ),
        None,
    )
