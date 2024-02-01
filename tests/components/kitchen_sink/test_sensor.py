"""The tests for the kitchen_sink sensor platform."""
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.kitchen_sink import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture
async def sensor_only() -> None:
    """Enable only the sensor platform."""
    with patch(
        "homeassistant.components.kitchen_sink.COMPONENTS_WITH_DEMO_PLATFORM",
        [Platform.SENSOR],
    ):
        yield


@pytest.fixture(autouse=True)
async def setup_comp(hass: HomeAssistant, sensor_only):
    """Set up demo component."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()


async def test_states(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test the expected sensor entities are added."""
    states = hass.states.async_all()
    assert set(states) == snapshot
