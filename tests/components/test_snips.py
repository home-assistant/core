"""Test the Snips component."""
import asyncio

from homeassistant.core import callback
from homeassistant.bootstrap import async_setup_component
from tests.common import async_fire_mqtt_message, async_mock_intent


@asyncio.coroutine
def test_snips_call_action(hass, mqtt_mock):
    """Test calling action via Snips."""
    result = yield from async_setup_component(hass, "snips", {
        "snips": {},
    })
    assert result
    payload = """
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

    intents = async_mock_intent(hass, 'Lights')

    async_fire_mqtt_message(hass, 'hermes/intent/Lights',
                            payload)
    yield from hass.async_block_till_done()
    assert len(intents) == 1
    intent = intents[0]
    assert intent.platform == 'snips'
    assert intent.intent_type == 'Lights'
    assert intent.slots == {'light_color': {'value': 'green'}}
    assert intent.text_input == 'turn the lights green'


@asyncio.coroutine
def test_snips_unknown_intent(hass, mqtt_mock):
    """Test calling action via Snips."""
    result = yield from async_setup_component(hass, "snips", {
        "snips": {},
    })
    assert result
    payload = """
    {
        "input": "what to do",
        "intent": {
            "intentName": "unknownIntent"
        },
        "slots": []
    }
    """
    intents = async_mock_intent(hass, 'knownIntent')

    async_fire_mqtt_message(hass, 'hermes/intent/unknownIntent',
                            payload)
    yield from hass.async_block_till_done()
    assert len(intents) == 1
    intent = intents[0]
    assert intent.platform == 'snips'
    assert intent.intent_type == 'unknownIntent'
    assert intent.text_input == 'what to do'


@asyncio.coroutine
def test_intent_response(hass, mqtt_mock):
    """Test intent response."""
    event = 'call_service'
    events = []

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    result = yield from async_setup_component(hass, "snips", {
        "snips": {},
    })
    assert result
    result = yield from async_setup_component(hass, "intent_script", {
        "intent_script": {
            "spokenIntent": {
                "speech": {
                    "type": "plain",
                    "text": "Hello",
                }
            }
        }
    })
    assert result
    payload = """
    {
        "input": "speak to me",
        "intent": {
            "intentName": "spokenIntent"
        },
        "slots": []
    }
    """
    async_fire_mqtt_message(hass, 'hermes/intent/spokenIntent',
                            payload)
    yield from hass.async_block_till_done()
    hass.bus.listen(event, record_event)
    # assert len(intents) == 1
    # intent = intents[0]
    # assert intent.platform == 'snips'
    # assert intent.intent_type == 'spokenIntent'
    # assert intent.text_input == 'speak to me'
    # assert len(events) == 0
