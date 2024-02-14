"""The tests for the valve platform."""

from homeassistant.components.valve import (
    DOMAIN,
    SERVICE_CLOSE_VALVE,
    SERVICE_OPEN_VALVE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service


async def test_open_valve_intent(hass: HomeAssistant) -> None:
    """Test HassTurnOn intent for valves."""
    assert await async_setup_component(hass, "intent", {})

    entity_id = f"{DOMAIN}.test_valve"
    hass.states.async_set(entity_id, "closed")
    calls = async_mock_service(hass, DOMAIN, SERVICE_OPEN_VALVE)

    response = await intent.async_handle(
        hass, "test", "HassTurnOn", {"name": {"value": "test valve"}}
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
    hass.states.async_set(entity_id, "opened")
    calls = async_mock_service(hass, DOMAIN, SERVICE_CLOSE_VALVE)

    response = await intent.async_handle(
        hass, "test", "HassTurnOff", {"name": {"value": "test valve"}}
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_CLOSE_VALVE
    assert call.data == {"entity_id": entity_id}
