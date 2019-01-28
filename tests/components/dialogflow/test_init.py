"""The tests for the Dialogflow component."""
import json
from unittest.mock import Mock

import pytest

from homeassistant import data_entry_flow
from homeassistant.components import dialogflow, intent_script
from homeassistant.core import callback
from homeassistant.setup import async_setup_component

SESSION_ID = "a9b84cec-46b6-484e-8f31-f65dba03ae6d"
INTENT_ID = "c6a74079-a8f0-46cd-b372-5a934d23591c"
INTENT_NAME = "tests"
REQUEST_ID = "19ef7e78-fe15-4e94-99dd-0c0b1e8753c3"
REQUEST_TIMESTAMP = "2017-01-21T17:54:18.952Z"
CONTEXT_NAME = "78a5db95-b7d6-4d50-9c9b-2fc73a5e34c3_id_dialog_context"


@pytest.fixture
async def calls(hass, fixture):
    """Return a list of Dialogflow calls triggered."""
    calls = []

    @callback
    def mock_service(call):
        """Mock action call."""
        calls.append(call)

    hass.services.async_register('test', 'dialogflow', mock_service)

    return calls


@pytest.fixture
async def fixture(hass, aiohttp_client):
    """Initialize a Home Assistant server for testing this module."""
    await async_setup_component(hass, dialogflow.DOMAIN, {
        "dialogflow": {},
    })
    await async_setup_component(hass, intent_script.DOMAIN, {
        "intent_script": {
            "WhereAreWeIntent": {
                "speech": {
                    "type": "plain",
                    "text": """
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
                }
            },
            "GetZodiacHoroscopeIntent": {
                "speech": {
                    "type": "plain",
                    "text": "You told us your sign is {{ ZodiacSign }}.",
                }
            },
            "CallServiceIntent": {
                "speech": {
                    "type": "plain",
                    "text": "Service called",
                },
                "action": {
                    "service": "test.dialogflow",
                    "data_template": {
                        "hello": "{{ ZodiacSign }}"
                    },
                    "entity_id": "switch.test",
                }
            }
        }
    })

    hass.config.api = Mock(base_url='http://example.com')
    result = await hass.config_entries.flow.async_init(
        'dialogflow',
        context={
            'source': 'user'
        }
    )
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM, result

    result = await hass.config_entries.flow.async_configure(
        result['flow_id'], {})
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    webhook_id = result['result'].data['webhook_id']

    return await aiohttp_client(hass.http.app), webhook_id


async def test_intent_action_incomplete(fixture):
    """Test when action is not completed."""
    mock_client, webhook_id = fixture
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

    response = await mock_client.post(
        '/api/webhook/{}'.format(webhook_id),
        data=json.dumps(data)
    )
    assert 200 == response.status
    assert "" == await response.text()


async def test_intent_slot_filling(fixture):
    """Test when Dialogflow asks for slot-filling return none."""
    mock_client, webhook_id = fixture
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

    response = await mock_client.post(
        '/api/webhook/{}'.format(webhook_id),
        data=json.dumps(data)
    )
    assert 200 == response.status
    assert "" == await response.text()


async def test_intent_request_with_parameters(fixture):
    """Test a request with parameters."""
    mock_client, webhook_id = fixture
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
    response = await mock_client.post(
        '/api/webhook/{}'.format(webhook_id),
        data=json.dumps(data)
    )
    assert 200 == response.status
    text = (await response.json()).get("speech")
    assert "You told us your sign is virgo." == text


async def test_intent_request_with_parameters_but_empty(fixture):
    """Test a request with parameters but empty value."""
    mock_client, webhook_id = fixture
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
    response = await mock_client.post(
        '/api/webhook/{}'.format(webhook_id),
        data=json.dumps(data)
    )
    assert 200 == response.status
    text = (await response.json()).get("speech")
    assert "You told us your sign is ." == text


async def test_intent_request_without_slots(hass, fixture):
    """Test a request without slots."""
    mock_client, webhook_id = fixture
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
    response = await mock_client.post(
        '/api/webhook/{}'.format(webhook_id),
        data=json.dumps(data)
    )
    assert 200 == response.status
    text = (await response.json()).get("speech")

    assert "Anne Therese is at unknown and Paulus is at unknown" == \
        text

    hass.states.async_set("device_tracker.paulus", "home")
    hass.states.async_set("device_tracker.anne_therese", "home")

    response = await mock_client.post(
        '/api/webhook/{}'.format(webhook_id),
        data=json.dumps(data)
    )
    assert 200 == response.status
    text = (await response.json()).get("speech")
    assert "You are both home, you silly" == text


async def test_intent_request_calling_service(fixture, calls):
    """Test a request for calling a service.

    If this request is done async the test could finish before the action
    has been executed. Hard to test because it will be a race condition.
    """
    mock_client, webhook_id = fixture
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
    response = await mock_client.post(
        '/api/webhook/{}'.format(webhook_id),
        data=json.dumps(data)
    )
    assert 200 == response.status
    assert call_count + 1 == len(calls)
    call = calls[-1]
    assert "test" == call.domain
    assert "dialogflow" == call.service
    assert ["switch.test"] == call.data.get("entity_id")
    assert "virgo" == call.data.get("hello")


async def test_intent_with_no_action(fixture):
    """Test an intent with no defined action."""
    mock_client, webhook_id = fixture
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
    response = await mock_client.post(
        '/api/webhook/{}'.format(webhook_id),
        data=json.dumps(data)
    )
    assert 200 == response.status
    text = (await response.json()).get("speech")
    assert \
        "You have not defined an action in your Dialogflow intent." == text


async def test_intent_with_unknown_action(fixture):
    """Test an intent with an action not defined in the conf."""
    mock_client, webhook_id = fixture
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
    response = await mock_client.post(
        '/api/webhook/{}'.format(webhook_id),
        data=json.dumps(data)
    )
    assert 200 == response.status
    text = (await response.json()).get("speech")
    assert \
        "This intent is not yet configured within Home Assistant." == text
