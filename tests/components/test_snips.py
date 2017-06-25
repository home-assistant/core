import asyncio

from homeassistant.bootstrap import async_setup_component
from tests.common import async_fire_mqtt_message, mock_service

EXAMPLE_MSG = """
{
    "text": "turn the lights green",
    "intent": {
        "intent_name": "Lights",
        "probability": 1
    },
    "slots": [
        {
            "slot_name": "light_color",
            "value": {
                "kind": "Custom",
                "value": "green"
            },
        }
    ]
}
"""

@asyncio.coroutine
def test_snips_call_action(hass, mqtt_mock):
    """Test calling action via Snips."""
    calls = mock_service(hass, 'test', 'service')

    result = yield from async_setup_component(hass, 'snips', {
        'snips': {
            'intents': {
                'Lights': {
                    'action': {
                        'service': 'test.service'
                    }
                }
            }
        }
    })
    assert result

    async_fire_mqtt_message(hass, 'hermes/nlu/intentParsed',
                            EXAMPLE_MSG)
    yield from hass.async_block_till_done()

    assert len(calls) == 1
