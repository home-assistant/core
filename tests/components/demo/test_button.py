"""The tests for the demo button component."""

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.button import DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

ENTITY_PUSH = "button.push"


@pytest.fixture
async def button_only() -> None:
    """Enable only the button platform."""
    with patch(
        "homeassistant.components.demo.COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM",
        [Platform.BUTTON],
    ):
        yield


@pytest.fixture(autouse=True)
async def setup_demo_button(hass: HomeAssistant, button_only) -> None:
    """Initialize setup demo button entity."""
    assert await async_setup_component(hass, DOMAIN, {"button": {"platform": "demo"}})
    await hass.async_block_till_done()


def test_setup_params(hass: HomeAssistant) -> None:
    """Test the initial parameters."""
    state = hass.states.get(ENTITY_PUSH)
    assert state
    assert state.state == STATE_UNKNOWN


async def test_press(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Test pressing the button."""
    state = hass.states.get(ENTITY_PUSH)
    assert state
    assert state.state == STATE_UNKNOWN

    now = dt_util.parse_datetime("2021-01-09 12:00:00+00:00")
    freezer.move_to(now)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: ENTITY_PUSH},
        blocking=True,
    )

    state = hass.states.get(ENTITY_PUSH)
    assert state
    assert state.state == now.isoformat()
