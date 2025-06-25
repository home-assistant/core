"""The tests for the valve platform."""

from homeassistant.components.valve import (
    ATTR_CURRENT_POSITION,
    DOMAIN,
    SERVICE_CLOSE_VALVE,
    SERVICE_OPEN_VALVE,
    SERVICE_SET_VALVE_POSITION,
    ValveState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service


async def test_open_valve_intent(hass: HomeAssistant) -> None:
    """Test HassTurnOn intent for valves."""
    assert await async_setup_component(hass, "intent", {})

    entity_id = f"{DOMAIN}.test_valve"
    hass.states.async_set(entity_id, ValveState.CLOSED)
    calls = async_mock_service(hass, DOMAIN, SERVICE_OPEN_VALVE)

    response = await intent.async_handle(
        hass, "test", intent.INTENT_TURN_ON, {"name": {"value": "test valve"}}
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_OPEN_VALVE
    assert call.data == {"entity_id": entity_id}


async def test_close_valve_intent(hass: HomeAssistant) -> None:
    """Test HassTurnOff intent for valves."""
    assert await async_setup_component(hass, "intent", {})

    entity_id = f"{DOMAIN}.test_valve"
    hass.states.async_set(entity_id, ValveState.OPEN)
    calls = async_mock_service(hass, DOMAIN, SERVICE_CLOSE_VALVE)

    response = await intent.async_handle(
        hass, "test", intent.INTENT_TURN_OFF, {"name": {"value": "test valve"}}
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_CLOSE_VALVE
    assert call.data == {"entity_id": entity_id}


async def test_set_valve_position(hass: HomeAssistant) -> None:
    """Test HassSetPosition intent for valves."""
    assert await async_setup_component(hass, "intent", {})

    entity_id = f"{DOMAIN}.test_valve"
    hass.states.async_set(
        entity_id, ValveState.CLOSED, attributes={ATTR_CURRENT_POSITION: 0}
    )
    calls = async_mock_service(hass, DOMAIN, SERVICE_SET_VALVE_POSITION)

    response = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_SET_POSITION,
        {"name": {"value": "test valve"}, "position": {"value": 50}},
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_SET_VALVE_POSITION
    assert call.data == {"entity_id": entity_id, "position": 50}
