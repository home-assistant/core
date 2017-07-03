"""Test the Snips component."""
import asyncio

from homeassistant.bootstrap import async_setup_component
from tests.common import async_fire_mqtt_message, async_mock_service

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
                "value": "blue"
            }
        }
    ]
}
"""


@asyncio.coroutine
def test_snips_call_action(hass, mqtt_mock):
    """Test calling action via Snips."""
    calls = async_mock_service(hass, 'test', 'service')

    result = yield from async_setup_component(hass, "snips", {
        "snips": {
            "intents": {
                "Lights": {
                    "action": {
                        "service": "test.service",
                        "data_template": {
                            "color": "{{ light_color }}"
                        }
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
    call = calls[0]
    assert call.data.get('color') == 'blue'
