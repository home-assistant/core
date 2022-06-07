"""Fixtures for Eight Sleep."""
import asyncio
from unittest.mock import patch

import pytest


@pytest.fixture(name="bypass", autouse=True)
def bypass_fixture():
    """Bypasses things that slow te tests down or block them from testing the behavior."""
    asyncio_sleep = asyncio.sleep

    async def sleep(duration, loop=None):
        await asyncio_sleep(0)

    with patch(
        "homeassistant.components.eight_sleep.config_flow.EightSleep.fetch_token",
    ), patch(
        "homeassistant.components.eight_sleep.config_flow.EightSleep.fetch_device_list",
    ), patch(
        "homeassistant.components.eight_sleep.config_flow.EightSleep.at_exit",
    ), patch(
        "homeassistant.components.eight_sleep.config_flow.asyncio.sleep", new=sleep
    ), patch(
        "homeassistant.components.eight_sleep.async_setup_entry",
        return_value=True,
    ), patch(
        "homeassistant.components.eight_sleep.config_flow.EightSleep.device_id",
        "device_id",
    ):
        yield


@pytest.fixture(name="valid_token")
def valid_token_fixture():
    """Return a valid token."""
    with patch(
        "homeassistant.components.eight_sleep.config_flow.EightSleep.token", "token"
    ):
        yield


@pytest.fixture(name="invalid_token")
def invalid_token_fixture():
    """Return an invalid token."""
    with patch(
        "homeassistant.components.eight_sleep.config_flow.EightSleep.token", None
    ):
        yield
