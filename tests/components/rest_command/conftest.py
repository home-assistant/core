"""Fixtures for the trend component tests."""

from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from homeassistant.components.rest_command import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component

type ComponentSetup = Callable[[dict[str, Any] | None], Awaitable[None]]

TEST_URL = "https://example.com/"
TEST_CONFIG = {
    "get_test": {"url": TEST_URL, "method": "get"},
    "patch_test": {"url": TEST_URL, "method": "patch"},
    "post_test": {"url": TEST_URL, "method": "post", "payload": "test"},
    "put_test": {"url": TEST_URL, "method": "put"},
    "delete_test": {"url": TEST_URL, "method": "delete"},
    "auth_test": {
        "url": TEST_URL,
        "method": "get",
        "username": "test",
        "password": "123456",
    },
}


@pytest.fixture(name="setup_component")
async def mock_setup_component(
    hass: HomeAssistant,
) -> ComponentSetup:
    """Set up the rest_command component."""

    async def _setup_func(alternative_config: dict[str, Any] | None = None) -> None:
        config = alternative_config or TEST_CONFIG
        with assert_setup_component(len(config)):
            await async_setup_component(hass, DOMAIN, {DOMAIN: config})

    return _setup_func
