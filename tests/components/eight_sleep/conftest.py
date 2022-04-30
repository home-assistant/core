"""Fixtures for Eight Sleep."""
from unittest.mock import PropertyMock, patch

import pytest


@pytest.fixture(name="bypass", autouse=True)
def bypass_fixture():
    """Bypasses things that slow te tests down or block them from testing the behavior."""
    with patch(
        "homeassistant.components.eight_sleep.config_flow.EightSleep.fetch_token",
    ), patch(
        "homeassistant.components.eight_sleep.config_flow.EightSleep.fetch_device_list",
    ), patch(
        "homeassistant.components.eight_sleep.config_flow.EightSleep.at_exit",
    ), patch(
        "homeassistant.components.eight_sleep.config_flow.asyncio.sleep",
    ), patch(
        "homeassistant.components.eight_sleep.async_setup_entry",
        return_value=True,
    ), patch(
        "homeassistant.components.eight_sleep.config_flow.EightSleep.deviceid",
        new_callable=PropertyMock(return_value="deviceid"),
    ):
        yield


@pytest.fixture(name="valid_token")
def valid_token_fixture():
    """Return a valid token."""
    with patch(
        "homeassistant.components.eight_sleep.config_flow.EightSleep.token",
        new_callable=PropertyMock(return_value="token"),
    ):
        yield


@pytest.fixture(name="invalid_token")
def invalid_token_fixture():
    """Return an invalid token."""
    with patch(
        "homeassistant.components.eight_sleep.config_flow.EightSleep.token",
        new_callable=PropertyMock(return_value=None),
    ):
        yield
