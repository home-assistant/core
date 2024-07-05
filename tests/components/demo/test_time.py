"""The tests for the demo time component."""

from unittest.mock import patch

import pytest

from homeassistant.components.time import ATTR_TIME, DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

ENTITY_TIME = "time.time"


@pytest.fixture
async def time_only() -> None:
    """Enable only the time platform."""
    with patch(
        "homeassistant.components.demo.COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM",
        [Platform.TIME],
    ):
        yield


@pytest.fixture(autouse=True)
async def setup_demo_datetime(hass: HomeAssistant, time_only) -> None:
    """Initialize setup demo time."""
    assert await async_setup_component(hass, DOMAIN, {"time": {"platform": "demo"}})
    await hass.async_block_till_done()


def test_setup_params(hass: HomeAssistant) -> None:
    """Test the initial parameters."""
    state = hass.states.get(ENTITY_TIME)
    assert state.state == "12:00:00"


async def test_set_value(hass: HomeAssistant) -> None:
    """Test set value service."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: ENTITY_TIME, ATTR_TIME: "01:02:03"},
        blocking=True,
    )
    state = hass.states.get(ENTITY_TIME)
    assert state.state == "01:02:03"
