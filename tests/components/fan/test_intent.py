"""Intent tests for the fan platform."""

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    DOMAIN,
    SERVICE_TURN_ON,
    intent as fan_intent,
)
from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from tests.common import async_mock_service


async def test_set_speed_intent(hass: HomeAssistant) -> None:
    """Test set speed intent for fans."""
    await fan_intent.async_setup_intents(hass)

    entity_id = f"{DOMAIN}.test_fan"
    hass.states.async_set(entity_id, STATE_OFF)
    calls = async_mock_service(hass, DOMAIN, SERVICE_TURN_ON)

    response = await intent.async_handle(
        hass,
        "test",
        fan_intent.INTENT_FAN_SET_SPEED,
        {"name": {"value": "test fan"}, ATTR_PERCENTAGE: {"value": 50}},
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert call.data == {"entity_id": entity_id, "percentage": 50}
