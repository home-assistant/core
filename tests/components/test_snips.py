"""The tests for the Dialogflow component."""
import unittest
#from unittest import mock

from homeassistant.core import callback
#from homeassistant import setup
from homeassistant.components import snips
from homeassistant.setup import async_setup_component, setup_component
from tests.common import (get_test_home_assistant, fire_mqtt_message,
                          mock_mqtt_component, mock_component, mock_service)

# An unknown action takes 8 s to return. Request timeout should be bigger to
# allow the test to finish
REQUEST_TIMEOUT = 15


class TestSnips(unittest.TestCase):
    """Test Snips."""
    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.calls = []

        mock_mqtt_component(self.hass)
        assert async_setup_component(self.hass, snips.DOMAIN, {
            "snips": {},
        })
        self.hass.start()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    @callback
    def record_calls(self, *args):
        """Helper for recording calls."""
        self.calls.append(args)

    def test_intent_call_service(self):
        """Test intent calling a service."""
        mock_component(self.hass, 'mqtt')
        setup_component(self.hass, snips.DOMAIN, {
            snips.DOMAIN: {},
        })
        setup_component(self.hass, "intent_script", {
            "intent_script": {
                "CallServiceIntent": {
                    "speech": {
                        "type": "plain",
                        "text": "Service called",
                    },
                    "action": {
                        "service": "test.snips",
                        "data_template": {
                            "zodiac_sign": "{{ ZodiacSign }}"
                        },
                        "entity_id": "switch.test",
                    }
                }
            }
        })

        service_calls = mock_service(self.hass, 'test', 'snips')
        payload = """
        {
            "input": "zodiac forecast for virgo",
            "sessionId": "abcdef1234567890",
            "intent": {
                "intentName": "CallServiceIntent"
            },
            "slots": [
                {
                    "slotName": "ZodiacSign",
                    "rawValue": "virgo",
                    "value": {
                        "kind": "custom",
                        "value": "virgo"
                    }
                }
            ]
        }
        """
        fire_mqtt_message(self.hass, 'hermes/intent/CallServiceIntent',
                          payload)
        self.hass.block_till_done()
        self.assertEqual(1, len(service_calls))
        self.assertEqual('virgo', service_calls[0].data['zodiac_sign'])
        self.assertEqual('switch.test', service_calls[0].data['entity_id'][0])

    def test_intent_with_snips_duration(self):
        """Test intent with snips duration."""
        mock_component(self.hass, 'mqtt')
        setup_component(self.hass, snips.DOMAIN, {
            snips.DOMAIN: {},
        })
        setup_component(self.hass, "intent_script", {
            "intent_script": {
                "SetTimer": {
                    "speech": {
                        "type": "plain",
                        "text": "Timer set {{ timer_duration }}",
                    },
                }
            }
        })
        payload = """
        {
            "input": "set a timer of five minutes",
            "intent": {
                "intentName": "SetTimer"
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
                    "entity": "snips/duration",
                    "slotName": "timer_duration"
                }
            ]
        }
        """
        with self.assertLogs(level='INFO') as test_handle:
            fire_mqtt_message(self.hass,
                              'hermes/intent/SetTimer', payload)
            self.hass.block_till_done()
            self.assertIn("payload={\"sessionId\": \"default\","
                          " \"text\": \"Timer set 300\"}",
                          test_handle.output[1])

    def test_intent_response(self):
        """Test intent response."""
        mock_component(self.hass, 'mqtt')
        setup_component(self.hass, snips.DOMAIN, {
            snips.DOMAIN: {},
        })
        setup_component(self.hass, "intent_script", {
            "intent_script": {
                "spokenIntent": {
                    "speech": {
                        "type": "plain",
                        "text": "Service called",
                    }
                }
            }
        })
        payload = """
        {
            "input": "speak to me",
            "sessionId": "abcdef1234567890",
            "intent": {
                "intentName": "spokenIntent"
            },
            "slots": []
        }
        """
        with self.assertLogs(level='INFO') as test_handle:
            fire_mqtt_message(self.hass,
                              'hermes/intent/CallServiceIntent', payload)
            self.hass.block_till_done()
            #print("test_handle:", test_handle.output[1])
            self.assertIn("payload={\"sessionId\": \"abcdef1234567890\","
                          " \"text\": \"Service called\"}",
                          test_handle.output[1])

    def test_unknown_intent(self):
        """Test unknown intent."""
        mock_mqtt_component(self.hass)
        setup_component(self.hass, snips.DOMAIN, {
            snips.DOMAIN: {},
        })
        payload = """
        {
            "input": "I don't know what I am supposed to do",
            "sessionId": "abcdef1234567890",
            "intent": {
                "intentName": "unknownIntent"
            },
            "slots": []
        }
        """
        #unsub = mqtt.subscribe(self.hass,
        #                       'hermes/dialogueManager/endSession',
        #                       self.record_calls)
        #print("self.calls:", self.calls)
        #self.assertEqual('hermes/dialogueManager/endSession',
        #                 self.calls[0][1])

        with self.assertLogs(level='WARNING') as test_handle:
            fire_mqtt_message(self.hass,
                              'hermes/intent/unknownIntent', payload)
            self.hass.block_till_done()
            self.assertIn("WARNING:homeassistant.components.snips:"
                          "Received unknown intent unknownIntent",
                          test_handle.output[0])
        # unsub()

    def test_intent_invalid_confg(self):
        """Test when intent has invalid config."""
        setup_component(self.hass, snips.DOMAIN, {
            "snips": {},
        })
        # intent should contain a slot.value.kind key
        payload = """
        {
            "input": "turn the lights green",
            "sessionId": "abcdef1234567890",
            "intent": {
                "intentName": "activateLights",
                "probability": 1
            },
            "slots": [
                {
                    "rawValue": "green",
                    "value": {
                        "value": "green"
                    },
                    "entity": "light_color",
                    "slotName": "light_color"
                }
            ]
        }
        """
        with self.assertLogs(level='ERROR') as test_handle:
            fire_mqtt_message(self.hass,
                              'hermes/intent/activateLights', payload)
            self.hass.block_till_done()
            self.assertIn("ERROR:homeassistant.components.snips:"
                          "Intent has invalid schema",
                          test_handle.output[0])
