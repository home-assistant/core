"""Fixtures for Eight Sleep."""
from unittest.mock import patch

from pyeight.exceptions import RequestError
import pytest


@pytest.fixture(name="bypass", autouse=True)
def bypass_fixture():
    """Bypasses things that slow te tests down or block them from testing the behavior."""
    with patch(
        "homeassistant.components.eight_sleep.config_flow.EightSleep.fetch_token",
    ), patch(
        "homeassistant.components.eight_sleep.config_flow.EightSleep.at_exit",
    ), patch(
        "homeassistant.components.eight_sleep.async_setup_entry",
        return_value=True,
    ):
        yield


@pytest.fixture(name="token_error")
def token_error_fixture():
    """Simulate error when fetching token."""
    with patch(
        "homeassistant.components.eight_sleep.config_flow.EightSleep.fetch_token",
        side_effect=RequestError,
    ):
        yield
