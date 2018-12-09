"""Test the Snips component."""
import json
import logging

import pytest
import voluptuous as vol

from homeassistant.bootstrap import async_setup_component
from homeassistant.components.mqtt import MQTT_PUBLISH_SCHEMA
import homeassistant.components.snips as snips
from homeassistant.helpers.intent import (ServiceIntentHandler, async_register)
from tests.common import (async_fire_mqtt_message, async_mock_intent,
                          async_mock_service)


async def test_snips_config(hass, mqtt_mock):
    """Test Snips Config."""
    result = await async_setup_component(hass, "snips", {
        "snips": {
            "feedback_sounds": True,
            "probability_threshold": .5,
            "site_ids": ["default", "remote"]
        },
    })
    assert result


async def test_snips_bad_config(hass, mqtt_mock):
    """Test Snips bad config."""
    result = await async_setup_component(hass, "snips", {
        "snips": {
            "feedback_sounds": "on",
            "probability": "none",
            "site_ids": "default"
        },
    })
    assert not result


async def test_snips_config_feedback_on(hass, mqtt_mock):
    """Test Snips Config."""
    calls = async_mock_service(hass, 'mqtt', 'publish', MQTT_PUBLISH_SCHEMA)
    result = await async_setup_component(hass, "snips", {
        "snips": {
            "feedback_sounds": True
        },
    })
    assert result
    await hass.async_block_till_done()

    assert len(calls) == 2
    topic = calls[0].data['topic']
    assert topic == 'hermes/feedback/sound/toggleOn'
    topic = calls[1].data['topic']
    assert topic == 'hermes/feedback/sound/toggleOn'
    assert calls[1].data['qos'] == 1
    assert calls[1].data['retain']


async def test_snips_config_feedback_off(hass, mqtt_mock):
    """Test Snips Config."""
    calls = async_mock_service(hass, 'mqtt', 'publish', MQTT_PUBLISH_SCHEMA)
    result = await async_setup_component(hass, "snips", {
        "snips": {
            "feedback_sounds": False
        },
    })
    assert result
    await hass.async_block_till_done()

    assert len(calls) == 2
    topic = calls[0].data['topic']
    assert topic == 'hermes/feedback/sound/toggleOn'
    topic = calls[1].data['topic']
    assert topic == 'hermes/feedback/sound/toggleOff'
    assert calls[1].data['qos'] == 0
    assert not calls[1].data['retain']


async def test_snips_config_no_feedback(hass, mqtt_mock):
    """Test Snips Config."""
    calls = async_mock_service(hass, 'snips', 'say')
    result = await async_setup_component(hass, "snips", {
        "snips": {},
    })
    assert result
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_snips_intent(hass, mqtt_mock):
    """Test intent via Snips."""
    result = await async_setup_component(hass, "snips", {
        "snips": {},
    })
    assert result
    payload = """
    {
        "siteId": "default",
        "sessionId": "1234567890ABCDEF",
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
                },
                "rawValue": "green"
            }
        ]
    }
    """

    intents = async_mock_intent(hass, 'Lights')

    async_fire_mqtt_message(hass, 'hermes/intent/Lights',
                            payload)
    await hass.async_block_till_done()
    assert len(intents) == 1
    intent = intents[0]
    assert intent.platform == 'snips'
    assert intent.intent_type == 'Lights'
    assert intent
    assert intent.slots == {'light_color': {'value': 'green'},
                            'light_color_raw': {'value': 'green'},
                            'probability': {'value': 1},
                            'site_id': {'value': 'default'},
                            'session_id': {'value': '1234567890ABCDEF'}}
    assert intent.text_input == 'turn the lights green'


async def test_snips_service_intent(hass, mqtt_mock):
    """Test ServiceIntentHandler via Snips."""
    hass.states.async_set('light.kitchen', 'off')
    calls = async_mock_service(hass, 'light', 'turn_on')
    result = await async_setup_component(hass, "snips", {
        "snips": {},
    })
    assert result
    payload = """
    {
        "input": "turn the light on",
        "intent": {
            "intentName": "Lights",
            "probability": 0.85
        },
        "siteId": "default",
        "slots": [
            {
                "slotName": "name",
                "value": {
                    "kind": "Custom",
                    "value": "kitchen"
                },
                "rawValue": "green"
            }
        ]
    }
    """

    async_register(hass, ServiceIntentHandler(
        "Lights", "light", 'turn_on', "Turned {} on"))

    async_fire_mqtt_message(hass, 'hermes/intent/Lights',
                            payload)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].domain == 'light'
    assert calls[0].service == 'turn_on'
    assert calls[0].data['entity_id'] == 'light.kitchen'
    assert 'probability' not in calls[0].data
    assert 'site_id' not in calls[0].data


async def test_snips_intent_with_duration(hass, mqtt_mock):
    """Test intent with Snips duration."""
    result = await async_setup_component(hass, "snips", {
        "snips": {},
    })
    assert result
    payload = """
    {
      "input": "set a timer of five minutes",
      "intent": {
        "intentName": "SetTimer",
        "probability": 1
      },
      "slots": [
        {
          "rawValue": "five minutes",
          "value": {
            "kind": "Duration",
            "years": 0,
            "quarters": 0,
            "months": 0,
            "weeks": 0,
            "days": 0,
            "hours": 0,
            "minutes": 5,
            "seconds": 0,
            "precision": "Exact"
          },
          "range": {
            "start": 15,
            "end": 27
          },
          "entity": "snips/duration",
          "slotName": "timer_duration"
        }
      ]
    }
    """
    intents = async_mock_intent(hass, 'SetTimer')

    async_fire_mqtt_message(hass, 'hermes/intent/SetTimer',
                            payload)
    await hass.async_block_till_done()
    assert len(intents) == 1
    intent = intents[0]
    assert intent.platform == 'snips'
    assert intent.intent_type == 'SetTimer'
    assert intent.slots == {'probability': {'value': 1},
                            'site_id': {'value': None},
                            'session_id': {'value': None},
                            'timer_duration': {'value': 300},
                            'timer_duration_raw': {'value': 'five minutes'}}


async def test_intent_speech_response(hass, mqtt_mock):
    """Test intent speech response via Snips."""
    calls = async_mock_service(hass, 'mqtt', 'publish', MQTT_PUBLISH_SCHEMA)
    result = await async_setup_component(hass, "snips", {
        "snips": {},
    })
    assert result
    result = await async_setup_component(hass, "intent_script", {
        "intent_script": {
            "spokenIntent": {
                "speech": {
                    "type": "plain",
                    "text": "I am speaking to you"
                }
            }
        }
    })
    assert result
    payload = """
    {
        "input": "speak to me",
        "sessionId": "abcdef0123456789",
        "intent": {
            "intentName": "spokenIntent",
            "probability": 1
        },
        "slots": []
    }
    """
    async_fire_mqtt_message(hass, 'hermes/intent/spokenIntent',
                            payload)
    await hass.async_block_till_done()

    assert len(calls) == 1
    payload = json.loads(calls[0].data['payload'])
    topic = calls[0].data['topic']
    assert payload['sessionId'] == 'abcdef0123456789'
    assert payload['text'] == 'I am speaking to you'
    assert topic == 'hermes/dialogueManager/endSession'


async def test_unknown_intent(hass, mqtt_mock, caplog):
    """Test unknown intent."""
    caplog.set_level(logging.WARNING)
    result = await async_setup_component(hass, "snips", {
        "snips": {},
    })
    assert result
    payload = """
    {
        "input": "I don't know what I am supposed to do",
        "sessionId": "abcdef1234567890",
        "intent": {
            "intentName": "unknownIntent",
            "probability": 1
        },
        "slots": []
    }
    """
    async_fire_mqtt_message(hass,
                            'hermes/intent/unknownIntent', payload)
    await hass.async_block_till_done()
    assert 'Received unknown intent unknownIntent' in caplog.text


async def test_snips_intent_user(hass, mqtt_mock):
    """Test intentName format user_XXX__intentName."""
    result = await async_setup_component(hass, "snips", {
        "snips": {},
    })
    assert result
    payload = """
    {
        "input": "what to do",
        "intent": {
            "intentName": "user_ABCDEF123__Lights",
            "probability": 1
        },
        "slots": []
    }
    """
    intents = async_mock_intent(hass, 'Lights')
    async_fire_mqtt_message(hass, 'hermes/intent/user_ABCDEF123__Lights',
                            payload)
    await hass.async_block_till_done()

    assert len(intents) == 1
    intent = intents[0]
    assert intent.platform == 'snips'
    assert intent.intent_type == 'Lights'


async def test_snips_intent_username(hass, mqtt_mock):
    """Test intentName format username:intentName."""
    result = await async_setup_component(hass, "snips", {
        "snips": {},
    })
    assert result
    payload = """
    {
        "input": "what to do",
        "intent": {
            "intentName": "username:Lights",
            "probability": 1
        },
        "slots": []
    }
    """
    intents = async_mock_intent(hass, 'Lights')
    async_fire_mqtt_message(hass, 'hermes/intent/username:Lights',
                            payload)
    await hass.async_block_till_done()

    assert len(intents) == 1
    intent = intents[0]
    assert intent.platform == 'snips'
    assert intent.intent_type == 'Lights'


async def test_snips_low_probability(hass, mqtt_mock, caplog):
    """Test intent via Snips."""
    caplog.set_level(logging.WARNING)
    result = await async_setup_component(hass, "snips", {
        "snips": {
            "probability_threshold": 0.5
        },
    })
    assert result
    payload = """
    {
        "input": "I am not sure what to say",
        "intent": {
            "intentName": "LightsMaybe",
            "probability": 0.49
        },
        "slots": []
    }
    """

    async_mock_intent(hass, 'LightsMaybe')
    async_fire_mqtt_message(hass, 'hermes/intent/LightsMaybe',
                            payload)
    await hass.async_block_till_done()
    assert 'Intent below probaility threshold 0.49 < 0.5' in caplog.text


async def test_intent_special_slots(hass, mqtt_mock):
    """Test intent special slot values via Snips."""
    calls = async_mock_service(hass, 'light', 'turn_on')
    result = await async_setup_component(hass, "snips", {
        "snips": {},
    })
    assert result
    result = await async_setup_component(hass, "intent_script", {
        "intent_script": {
            "Lights": {
                "action": {
                    "service": "light.turn_on",
                    "data_template": {
                        "probability": "{{ probability }}",
                        "site_id": "{{ site_id }}"
                    }
                }
            }
        }
    })
    assert result
    payload = """
    {
        "input": "turn the light on",
        "intent": {
            "intentName": "Lights",
            "probability": 0.85
        },
        "siteId": "default",
        "slots": []
    }
    """
    async_fire_mqtt_message(hass, 'hermes/intent/Lights', payload)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].domain == 'light'
    assert calls[0].service == 'turn_on'
    assert calls[0].data['probability'] == '0.85'
    assert calls[0].data['site_id'] == 'default'


async def test_snips_say(hass, caplog):
    """Test snips say with invalid config."""
    calls = async_mock_service(hass, 'snips', 'say', snips.SERVICE_SCHEMA_SAY)
    data = {'text': 'Hello'}
    await hass.services.async_call('snips', 'say', data)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].domain == 'snips'
    assert calls[0].service == 'say'
    assert calls[0].data['text'] == 'Hello'


async def test_snips_say_action(hass, caplog):
    """Test snips say_action with invalid config."""
    calls = async_mock_service(hass, 'snips', 'say_action',
                               snips.SERVICE_SCHEMA_SAY_ACTION)

    data = {'text': 'Hello', 'intent_filter': ['myIntent']}
    await hass.services.async_call('snips', 'say_action', data)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].domain == 'snips'
    assert calls[0].service == 'say_action'
    assert calls[0].data['text'] == 'Hello'
    assert calls[0].data['intent_filter'] == ['myIntent']


async def test_snips_say_invalid_config(hass, caplog):
    """Test snips say with invalid config."""
    calls = async_mock_service(hass, 'snips', 'say',
                               snips.SERVICE_SCHEMA_SAY)

    data = {'text': 'Hello', 'badKey': 'boo'}
    with pytest.raises(vol.Invalid):
        await hass.services.async_call('snips', 'say', data)
    await hass.async_block_till_done()

    assert len(calls) == 0


async def test_snips_say_action_invalid(hass, caplog):
    """Test snips say_action with invalid config."""
    calls = async_mock_service(hass, 'snips', 'say_action',
                               snips.SERVICE_SCHEMA_SAY_ACTION)

    data = {'text': 'Hello', 'can_be_enqueued': 'notabool'}

    with pytest.raises(vol.Invalid):
        await hass.services.async_call('snips', 'say_action', data)
    await hass.async_block_till_done()

    assert len(calls) == 0


async def test_snips_feedback_on(hass, caplog):
    """Test snips say with invalid config."""
    calls = async_mock_service(hass, 'snips', 'feedback_on',
                               snips.SERVICE_SCHEMA_FEEDBACK)

    data = {'site_id': 'remote'}
    await hass.services.async_call('snips', 'feedback_on', data)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].domain == 'snips'
    assert calls[0].service == 'feedback_on'
    assert calls[0].data['site_id'] == 'remote'


async def test_snips_feedback_off(hass, caplog):
    """Test snips say with invalid config."""
    calls = async_mock_service(hass, 'snips', 'feedback_off',
                               snips.SERVICE_SCHEMA_FEEDBACK)

    data = {'site_id': 'remote'}
    await hass.services.async_call('snips', 'feedback_off', data)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].domain == 'snips'
    assert calls[0].service == 'feedback_off'
    assert calls[0].data['site_id'] == 'remote'


async def test_snips_feedback_config(hass, caplog):
    """Test snips say with invalid config."""
    calls = async_mock_service(hass, 'snips', 'feedback_on',
                               snips.SERVICE_SCHEMA_FEEDBACK)

    data = {'site_id': 'remote', 'test': 'test'}
    with pytest.raises(vol.Invalid):
        await hass.services.async_call('snips', 'feedback_on', data)
    await hass.async_block_till_done()

    assert len(calls) == 0
