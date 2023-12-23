"""Fixtures for the trend component tests."""
from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from homeassistant.components.trend.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ComponentSetup = Callable[[dict[str, Any]], Awaitable[None]]


@pytest.fixture(name="config_entry")
async def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a MockConfigEntry for testing."""
    return MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My trend",
            "entity_id": "sensor.cpu_temp",
            "invert": False,
            "max_samples": 2.0,
            "min_gradient": 0.0,
            "sample_duration": 0.0,
        },
        title="My trend",
    )


@pytest.fixture(name="setup_component")
async def mock_setup_component(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> ComponentSetup:
    """Set up the trend component."""

    async def _setup_func(component_params: dict[str, Any]) -> None:
        config_entry.title = "test_trend_sensor"
        config_entry.options = {
            **config_entry.options,
            **component_params,
            "name": "test_trend_sensor",
            "entity_id": "sensor.test_state",
        }
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return _setup_func
