"""The tests for the valve platform."""
from homeassistant.components.valve import (
    SERVICE_CLOSE_VALVE,
    SERVICE_OPEN_VALVE,
    intent as valve_intent,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from tests.common import async_mock_service


async def test_open_valve_intent(hass: HomeAssistant) -> None:
    """Test HassOpenValve intent."""
    await valve_intent.async_setup_intents(hass)

    hass.states.async_set("valve.garage_door", "closed")
    calls = async_mock_service(hass, "valve", SERVICE_OPEN_VALVE)

    response = await intent.async_handle(
        hass, "test", "HassOpenValve", {"name": {"value": "garage door"}}
    )
    await hass.async_block_till_done()

    assert response.speech["plain"]["speech"] == "Opened garage door"
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == "valve"
    assert call.service == "open_valve"
    assert call.data == {"entity_id": "valve.garage_door"}


async def test_close_valve_intent(hass: HomeAssistant) -> None:
    """Test HassCloseValve intent."""
    await valve_intent.async_setup_intents(hass)

    hass.states.async_set("valve.garage_door", "open")
    calls = async_mock_service(hass, "valve", SERVICE_CLOSE_VALVE)

    response = await intent.async_handle(
        hass, "test", "HassCloseValve", {"name": {"value": "garage door"}}
    )
    await hass.async_block_till_done()

    assert response.speech["plain"]["speech"] == "Closed garage door"
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == "valve"
    assert call.service == "close_valve"
    assert call.data == {"entity_id": "valve.garage_door"}
