"""Fixtures for Trend integration tests."""
from collections.abc import Awaitable, Callable
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

ComponentSetup = Callable[[dict[str, Any]], Awaitable[None]]


async def setup_component(hass: HomeAssistant, params: dict) -> None:
    """Set up the trend component."""
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
