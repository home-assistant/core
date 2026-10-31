"""Tests for the Besen integration."""

from collections.abc import Callable
from unittest.mock import Mock

from besen.models import BesenData
import pytest


def find_besen_update_callback(mock: Mock) -> Callable[[BesenData], None]:
    """Find the registered Besen update callback."""

    if not mock.add_listener.call_args_list:
        pytest.fail("Besen update callback was not registered")
    return mock.add_listener.call_args.args[0]


def publish_besen_state(mock: Mock, state: BesenData) -> None:
    """Publish a state update from the mocked Besen client."""

    mock.state = state
    find_besen_update_callback(mock)(state)
