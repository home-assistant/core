"""The tests for the demo text component."""
import pytest

from homeassistant.components.text import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_PATTERN,
    ATTR_VALUE,
    DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_MODE, MAX_LENGTH_STATE_STATE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

ENTITY_TEXT = "text.text"


@pytest.fixture(autouse=True)
async def setup_demo_text(hass):
    """Initialize setup demo text."""
    assert await async_setup_component(hass, DOMAIN, {"text": {"platform": "demo"}})
    await hass.async_block_till_done()


def test_setup_params(hass: HomeAssistant) -> None:
    """Test the initial parameters."""
    state = hass.states.get(ENTITY_TEXT)
    assert state.state == "Hello world"
    assert state.attributes[ATTR_MIN] == 0
    assert state.attributes[ATTR_MAX] == MAX_LENGTH_STATE_STATE
    assert state.attributes[ATTR_PATTERN] is None
    assert state.attributes[ATTR_MODE] == "text"


async def test_set_value(hass: HomeAssistant) -> None:
    """Test set value service."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: ENTITY_TEXT, ATTR_VALUE: "new"},
        blocking=True,
    )
    state = hass.states.get(ENTITY_TEXT)
    assert state.state == "new"
