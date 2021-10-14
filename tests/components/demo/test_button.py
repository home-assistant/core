"""The tests for the demo button component."""

from unittest.mock import patch

import pytest

from homeassistant.components.button.const import DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

ENTITY_PUSH = "button.push"


@pytest.fixture(autouse=True)
async def setup_demo_button(hass: HomeAssistant) -> None:
    """Initialize setup demo button entity."""
    assert await async_setup_component(hass, DOMAIN, {"button": {"platform": "demo"}})
    await hass.async_block_till_done()


def test_setup_params(hass: HomeAssistant) -> None:
    """Test the initial parameters."""
    state = hass.states.get(ENTITY_PUSH)
    assert state
    assert state.state == STATE_UNKNOWN


async def test_press(hass: HomeAssistant) -> None:
    """Test pressing the button."""
    state = hass.states.get(ENTITY_PUSH)
    assert state
    assert state.state == STATE_UNKNOWN

    now = dt_util.parse_datetime("2021-01-09 12:00:00+00:00")
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: ENTITY_PUSH},
            blocking=True,
        )

    state = hass.states.get(ENTITY_PUSH)
    assert state
    assert state.state == now.isoformat()
