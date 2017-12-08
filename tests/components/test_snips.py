"""Test the Snips component."""
import asyncio

from homeassistant.bootstrap import async_setup_component
from tests.common import async_fire_mqtt_message, async_mock_intent

EXAMPLE_MSG = """
{
    "input": "turn the lights green",
    "intent": {
        "intentName": "Lights",
        "probability": 1
    },
    "slots": [
        {
            "slotName": "light_color",
            "value": {
                "kind": "Custom",
                "value": "green"
            }
        }
    ]
}
"""


@asyncio.coroutine
def test_snips_call_action(hass, mqtt_mock):
    """Test calling action via Snips."""
    result = yield from async_setup_component(hass, "snips", {
        "snips": {},
    })
    assert result

    intents = async_mock_intent(hass, 'Lights')

    async_fire_mqtt_message(hass, 'hermes/intent/activateLights',
                            EXAMPLE_MSG)
    yield from hass.async_block_till_done()
    assert len(intents) == 1
    intent = intents[0]
    assert intent.platform == 'snips'
    assert intent.intent_type == 'Lights'
    assert intent.slots == {'light_color': {'value': 'green'}}
    assert intent.text_input == 'turn the lights green'
