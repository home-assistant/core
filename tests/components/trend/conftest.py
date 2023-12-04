"""Fixtures for Trend integration tests."""
from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

ComponentSetup = Callable[[dict[str, Any]], Awaitable[None]]


@pytest.fixture
async def setup_component(hass: HomeAssistant) -> ComponentSetup:
    """Set up the trend component."""

    async def _inner_setup(params: dict[str, Any]) -> None:
        assert await async_setup_component(
            hass,
            "binary_sensor",
            {
                "binary_sensor": {
                    "platform": "trend",
                    "sensors": {
                        "test_trend_sensor": params,
                    },
                }
            },
        )
        await hass.async_block_till_done()

    return _inner_setup
