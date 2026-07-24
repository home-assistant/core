"""Test the EvolvIOT switch platform."""

import pytest

from homeassistant.components.evolviot.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import UNIQUE_ID, MockEvolvIOTWebSocket


@pytest.mark.usefixtures("setup_integration")
async def test_switch_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test switch setup from WebSocket ready data."""
    entity_id = entity_registry.async_get_entity_id(SWITCH_DOMAIN, DOMAIN, UNIQUE_ID)

    state = hass.states.get(entity_id)

    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("setup_integration")
async def test_switch_push_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_websocket: MockEvolvIOTWebSocket,
) -> None:
    """Test WebSocket state pushes update the switch."""
    entity_id = entity_registry.async_get_entity_id(SWITCH_DOMAIN, DOMAIN, UNIQUE_ID)

    await mock_websocket.emit_state("on")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.usefixtures("setup_integration")
async def test_switch_sends_commands(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_websocket: MockEvolvIOTWebSocket,
) -> None:
    """Test switch commands are sent through pyevolviot."""
    entity_id = entity_registry.async_get_entity_id(SWITCH_DOMAIN, DOMAIN, UNIQUE_ID)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": entity_id},
        blocking=True,
    )

    assert mock_websocket.commands[-1] == ("switch.evolviot_switch", "turn_on")
    state = hass.states.get(entity_id)

    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {"entity_id": entity_id},
        blocking=True,
    )

    assert mock_websocket.commands[-1] == ("switch.evolviot_switch", "turn_off")
    state = hass.states.get(entity_id)

    assert state is not None
    assert state.state == STATE_OFF
