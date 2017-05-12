"""The tests for the APIAI component."""
# pylint: disable=protected-access
import json
import unittest

import requests

from homeassistant.core import callback
from homeassistant import setup, const
from homeassistant.components import apiai, http

from tests.common import get_test_instance_port, get_test_home_assistant

API_PASSWORD = "test1234"
SERVER_PORT = get_test_instance_port()
BASE_API_URL = "http://127.0.0.1:{}".format(SERVER_PORT)
INTENTS_API_URL = "{}{}".format(BASE_API_URL, apiai.INTENTS_API_ENDPOINT)

HA_HEADERS = {
    const.HTTP_HEADER_HA_AUTH: API_PASSWORD,
    const.HTTP_HEADER_CONTENT_TYPE: const.CONTENT_TYPE_JSON,
}

SESSION_ID = "a9b84cec-46b6-484e-8f31-f65dba03ae6d"
INTENT_ID = "c6a74079-a8f0-46cd-b372-5a934d23591c"
INTENT_NAME = "tests"
REQUEST_ID = "19ef7e78-fe15-4e94-99dd-0c0b1e8753c3"
REQUEST_TIMESTAMP = "2017-01-21T17:54:18.952Z"
CONTEXT_NAME = "78a5db95-b7d6-4d50-9c9b-2fc73a5e34c3_id_dialog_context"
MAX_RESPONSE_TIME = 5  # https://docs.api.ai/docs/webhook

# An unknown action takes 8s to return. Request timeout should be bigger to
# allow the test to finish
REQUEST_TIMEOUT = 15

# pylint: disable=invalid-name
hass = None
calls = []


# pylint: disable=invalid-name
def setUpModule():
    """Initialize a Home Assistant server for testing this module."""
    global hass

    hass = get_test_home_assistant()

    setup.setup_component(
        hass, http.DOMAIN,
        {http.DOMAIN: {http.CONF_API_PASSWORD: API_PASSWORD,
                       http.CONF_SERVER_PORT: SERVER_PORT}})

    @callback
    def mock_service(call):
        """Mock action call."""
        calls.append(call)

    hass.services.register("test", "apiai", mock_service)

    setup.setup_component(hass, apiai.DOMAIN, {
        # Key is here to verify we allow other keys in config too
        "homeassistant": {},
        "apiai": {
            "intents": {
                "WhereAreWeIntent": {
                    "speech":
                    """
                        {%- if is_state("device_tracker.paulus", "home")
                               and is_state("device_tracker.anne_therese",
                                            "home") -%}
                            You are both home, you silly
                        {%- else -%}
                            Anne Therese is at {{
                                states("device_tracker.anne_therese")
                            }} and Paulus is at {{
                                states("device_tracker.paulus")
                            }}
                        {% endif %}
                    """,
                },
                "GetZodiacHoroscopeIntent": {
                    "speech": "You told us your sign is {{ ZodiacSign }}.",
                },
                "CallServiceIntent": {
                    "speech": "Service called",
                    "action": {
                        "service": "test.apiai",
                        "data_template": {
                            "hello": "{{ ZodiacSign }}"
                        },
                        "entity_id": "switch.test",
                    }
                }
            }
        }
    })

    hass.start()


# pylint: disable=invalid-name
def tearDownModule():
    """Stop the Home Assistant server."""
    hass.stop()


def _intent_req(data):
    return requests.post(INTENTS_API_URL, data=json.dumps(data),
                         timeout=REQUEST_TIMEOUT, headers=HA_HEADERS)


class TestApiai(unittest.TestCase):
    """Test APIAI."""

    def tearDown(self):
        """Stop everything that was started."""
        hass.block_till_done()

    def test_intent_action_incomplete(self):
        """Test when action is not completed."""
        data = {
            "id": REQUEST_ID,
            "timestamp": REQUEST_TIMESTAMP,
            "result": {
                "source": "agent",
                "resolvedQuery": "my zodiac sign is virgo",
                "speech": "",
                "action": "GetZodiacHoroscopeIntent",
                "actionIncomplete": True,
                "parameters": {
                    "ZodiacSign": "virgo"
                },
                "metadata": {
                    "intentId": INTENT_ID,
                    "webhookUsed": "true",
                    "webhookForSlotFillingUsed": "false",
                    "intentName": INTENT_NAME
                },
                "fulfillment": {
                    "speech": "",
                    "messages": [
                        {
                            "type": 0,
                            "speech": ""
                        }
                    ]
                },
                "score": 1
            },
            "status": {
                "code": 200,
                "errorType": "success"
            },
            "sessionId": SESSION_ID,
            "originalRequest": None
        }

        req = _intent_req(data)
        self.assertEqual(200, req.status_code)
        self.assertEqual("", req.text)

    def test_intent_slot_filling(self):
        """Test when API.AI asks for slot-filling return none."""
        data = {
            "id": REQUEST_ID,
            "timestamp": REQUEST_TIMESTAMP,
            "result": {
                "source": "agent",
                "resolvedQuery": "my zodiac sign is",
                "speech": "",
                "action": "GetZodiacHoroscopeIntent",
                "actionIncomplete": True,
                "parameters": {
                    "ZodiacSign": ""
                },
                "contexts": [
                    {
                        "name": CONTEXT_NAME,
                        "parameters": {
                            "ZodiacSign.original": "",
                            "ZodiacSign": ""
                        },
                        "lifespan": 2
                    },
                    {
                        "name": "tests_ha_dialog_context",
                        "parameters": {
                            "ZodiacSign.original": "",
                            "ZodiacSign": ""
                        },
                        "lifespan": 2
                    },
                    {
                        "name": "tests_ha_dialog_params_zodiacsign",
                        "parameters": {
                            "ZodiacSign.original": "",
                            "ZodiacSign": ""
                        },
                        "lifespan": 1
                    }
                ],
                "metadata": {
                    "intentId": INTENT_ID,
                    "webhookUsed": "true",
                    "webhookForSlotFillingUsed": "true",
                    "intentName": INTENT_NAME
                },
                "fulfillment": {
                    "speech": "What is the ZodiacSign?",
                    "messages": [
                        {
                            "type": 0,
                            "speech": "What is the ZodiacSign?"
                        }
                    ]
                },
                "score": 0.77
            },
            "status": {
                "code": 200,
                "errorType": "success"
            },
            "sessionId": SESSION_ID,
            "originalRequest": None
        }

        req = _intent_req(data)
        self.assertEqual(200, req.status_code)
        self.assertEqual("", req.text)

    def test_intent_request_with_parameters(self):
        """Test a request with parameters."""
        data = {
            "id": REQUEST_ID,
            "timestamp": REQUEST_TIMESTAMP,
            "result": {
                "source": "agent",
                "resolvedQuery": "my zodiac sign is virgo",
                "speech": "",
                "action": "GetZodiacHoroscopeIntent",
                "actionIncomplete": False,
                "parameters": {
                    "ZodiacSign": "virgo"
                },
                "contexts": [],
                "metadata": {
                    "intentId": INTENT_ID,
                    "webhookUsed": "true",
                    "webhookForSlotFillingUsed": "false",
                    "intentName": INTENT_NAME
                },
                "fulfillment": {
                    "speech": "",
                    "messages": [
                        {
                            "type": 0,
                            "speech": ""
                        }
                    ]
                },
                "score": 1
            },
            "status": {
                "code": 200,
                "errorType": "success"
            },
            "sessionId": SESSION_ID,
            "originalRequest": None
        }
        req = _intent_req(data)
        self.assertEqual(200, req.status_code)
        text = req.json().get("speech")
        self.assertEqual("You told us your sign is virgo.", text)

    def test_intent_request_with_parameters_but_empty(self):
        """Test a request with parameters but empty value."""
        data = {
            "id": REQUEST_ID,
            "timestamp": REQUEST_TIMESTAMP,
            "result": {
                "source": "agent",
                "resolvedQuery": "my zodiac sign is virgo",
                "speech": "",
                "action": "GetZodiacHoroscopeIntent",
                "actionIncomplete": False,
                "parameters": {
                    "ZodiacSign": ""
                },
                "contexts": [],
                "metadata": {
                    "intentId": INTENT_ID,
                    "webhookUsed": "true",
                    "webhookForSlotFillingUsed": "false",
                    "intentName": INTENT_NAME
                },
                "fulfillment": {
                    "speech": "",
                    "messages": [
                        {
                            "type": 0,
                            "speech": ""
                        }
                    ]
                },
                "score": 1
            },
            "status": {
                "code": 200,
                "errorType": "success"
            },
            "sessionId": SESSION_ID,
            "originalRequest": None
        }
        req = _intent_req(data)
        self.assertEqual(200, req.status_code)
        text = req.json().get("speech")
        self.assertEqual("You told us your sign is .", text)

    def test_intent_request_without_slots(self):
        """Test a request without slots."""
        data = {
            "id": REQUEST_ID,
            "timestamp": REQUEST_TIMESTAMP,
            "result": {
                "source": "agent",
                "resolvedQuery": "where are we",
                "speech": "",
                "action": "WhereAreWeIntent",
                "actionIncomplete": False,
                "parameters": {},
                "contexts": [],
                "metadata": {
                    "intentId": INTENT_ID,
                    "webhookUsed": "true",
                    "webhookForSlotFillingUsed": "false",
                    "intentName": INTENT_NAME
                },
                "fulfillment": {
                    "speech": "",
                    "messages": [
                        {
                            "type": 0,
                            "speech": ""
                        }
                    ]
                },
                "score": 1
            },
            "status": {
                "code": 200,
                "errorType": "success"
            },
            "sessionId": SESSION_ID,
            "originalRequest": None
        }
        req = _intent_req(data)
        self.assertEqual(200, req.status_code)
        text = req.json().get("speech")

        self.assertEqual("Anne Therese is at unknown and Paulus is at unknown",
                         text)

        hass.states.set("device_tracker.paulus", "home")
        hass.states.set("device_tracker.anne_therese", "home")

        req = _intent_req(data)
        self.assertEqual(200, req.status_code)
        text = req.json().get("speech")
        self.assertEqual("You are both home, you silly", text)

    def test_intent_request_calling_service(self):
        """Test a request for calling a service.

        If this request is done async the test could finish before the action
        has been executed. Hard to test because it will be a race condition.
        """
        data = {
            "id": REQUEST_ID,
            "timestamp": REQUEST_TIMESTAMP,
            "result": {
                "source": "agent",
                "resolvedQuery": "my zodiac sign is virgo",
                "speech": "",
                "action": "CallServiceIntent",
                "actionIncomplete": False,
                "parameters": {
                    "ZodiacSign": "virgo"
                },
                "contexts": [],
                "metadata": {
                    "intentId": INTENT_ID,
                    "webhookUsed": "true",
                    "webhookForSlotFillingUsed": "false",
                    "intentName": INTENT_NAME
                },
                "fulfillment": {
                    "speech": "",
                    "messages": [
                        {
                            "type": 0,
                            "speech": ""
                        }
                    ]
                },
                "score": 1
            },
            "status": {
                "code": 200,
                "errorType": "success"
            },
            "sessionId": SESSION_ID,
            "originalRequest": None
        }
        call_count = len(calls)
        req = _intent_req(data)
        self.assertEqual(200, req.status_code)
        self.assertEqual(call_count + 1, len(calls))
        call = calls[-1]
        self.assertEqual("test", call.domain)
        self.assertEqual("apiai", call.service)
        self.assertEqual(["switch.test"], call.data.get("entity_id"))
        self.assertEqual("virgo", call.data.get("hello"))

    def test_intent_with_no_action(self):
        """Test a intent with no defined action."""
        data = {
            "id": REQUEST_ID,
            "timestamp": REQUEST_TIMESTAMP,
            "result": {
                "source": "agent",
                "resolvedQuery": "my zodiac sign is virgo",
                "speech": "",
                "action": "",
                "actionIncomplete": False,
                "parameters": {
                    "ZodiacSign": ""
                },
                "contexts": [],
                "metadata": {
                    "intentId": INTENT_ID,
                    "webhookUsed": "true",
                    "webhookForSlotFillingUsed": "false",
                    "intentName": INTENT_NAME
                },
                "fulfillment": {
                    "speech": "",
                    "messages": [
                        {
                            "type": 0,
                            "speech": ""
                        }
                    ]
                },
                "score": 1
            },
            "status": {
                "code": 200,
                "errorType": "success"
            },
            "sessionId": SESSION_ID,
            "originalRequest": None
        }
        req = _intent_req(data)
        self.assertEqual(200, req.status_code)
        text = req.json().get("speech")
        self.assertEqual(
            "You have not defined an action in your api.ai intent.", text)

    def test_intent_with_unknown_action(self):
        """Test a intent with an action not defined in the conf."""
        data = {
            "id": REQUEST_ID,
            "timestamp": REQUEST_TIMESTAMP,
            "result": {
                "source": "agent",
                "resolvedQuery": "my zodiac sign is virgo",
                "speech": "",
                "action": "unknown",
                "actionIncomplete": False,
                "parameters": {
                    "ZodiacSign": ""
                },
                "contexts": [],
                "metadata": {
                    "intentId": INTENT_ID,
                    "webhookUsed": "true",
                    "webhookForSlotFillingUsed": "false",
                    "intentName": INTENT_NAME
                },
                "fulfillment": {
                    "speech": "",
                    "messages": [
                        {
                            "type": 0,
                            "speech": ""
                        }
                    ]
                },
                "score": 1
            },
            "status": {
                "code": 200,
                "errorType": "success"
            },
            "sessionId": SESSION_ID,
            "originalRequest": None
        }
        req = _intent_req(data)
        self.assertEqual(200, req.status_code)
        text = req.json().get("speech")
        self.assertEqual(
            "Intent 'unknown' is not yet configured within Home Assistant.",
            text)
