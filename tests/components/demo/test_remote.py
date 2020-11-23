"""The tests for the demo remote component."""
import pytest

import homeassistant.components.remote as remote
from homeassistant.components.remote import ATTR_COMMAND
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.setup import async_setup_component

ENTITY_ID = "remote.remote_one"
SERVICE_SEND_COMMAND = "send_command"


@pytest.fixture(autouse=True)
async def setup_component(hass):
    """Initialize components."""
    assert await async_setup_component(
        hass, remote.DOMAIN, {"remote": {"platform": "demo"}}
    )
    await hass.async_block_till_done()


async def test_methods(hass):
    """Test if services call the entity methods as expected."""
    await hass.services.async_call(
        remote.DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}
    )
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON

    await hass.services.async_call(
        remote.DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}
    )
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF

    await hass.services.async_call(
        remote.DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}
    )
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_COMMAND: ["test"],
    }

    await hass.services.async_call(remote.DOMAIN, SERVICE_SEND_COMMAND, data)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state.attributes == {
        "friendly_name": "Remote One",
        "last_command_sent": "test",
        "supported_features": 0,
    }
