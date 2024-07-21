"""The tests for the Dialogflow component."""

import copy
from http import HTTPStatus
import json

import pytest

from homeassistant import config_entries
from homeassistant.components import dialogflow, intent_script
from homeassistant.config import async_process_ha_core_config
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from tests.typing import ClientSessionGenerator

SESSION_ID = "a9b84cec-46b6-484e-8f31-f65dba03ae6d"
INTENT_ID = "c6a74079-a8f0-46cd-b372-5a934d23591c"
INTENT_NAME = "tests"
REQUEST_ID = "19ef7e78-fe15-4e94-99dd-0c0b1e8753c3"
REQUEST_TIMESTAMP = "2017-01-21T17:54:18.952Z"
CONTEXT_NAME = "78a5db95-b7d6-4d50-9c9b-2fc73a5e34c3_id_dialog_context"


@pytest.fixture
async def calls(hass: HomeAssistant, fixture) -> list[ServiceCall]:
    """Return a list of Dialogflow calls triggered."""
    calls: list[ServiceCall] = []

    @callback
    def mock_service(call: ServiceCall) -> None:
        """Mock action call."""
        calls.append(call)

    hass.services.async_register("test", "dialogflow", mock_service)

    return calls


@pytest.fixture
async def fixture(hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator):
    """Initialize a Home Assistant server for testing this module."""
    await async_setup_component(hass, dialogflow.DOMAIN, {"dialogflow": {}})
    await async_setup_component(
        hass,
        intent_script.DOMAIN,
        {
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
                    "speech": {"type": "plain", "text": "Service called"},
                    "action": {
                        "service": "test.dialogflow",
                        "data_template": {"hello": "{{ ZodiacSign }}"},
                        "entity_id": "switch.test",
                    },
                },
            }
        },
    )

    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )

    result = await hass.config_entries.flow.async_init(
        "dialogflow", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM, result

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    webhook_id = result["result"].data["webhook_id"]

    return await hass_client_no_auth(), webhook_id


class _Data:
    _v1 = {
        "id": REQUEST_ID,
        "timestamp": REQUEST_TIMESTAMP,
        "result": {
            "source": "agent",
            "resolvedQuery": "my zodiac sign is virgo",
            "action": "GetZodiacHoroscopeIntent",
            "actionIncomplete": False,
            "parameters": {"ZodiacSign": "virgo"},
            "metadata": {
                "intentId": INTENT_ID,
                "webhookUsed": "true",
                "webhookForSlotFillingUsed": "false",
                "intentName": INTENT_NAME,
            },
            "fulfillment": {"speech": "", "messages": [{"type": 0, "speech": ""}]},
            "score": 1,
        },
        "status": {"code": 200, "errorType": "success"},
        "sessionId": SESSION_ID,
        "originalRequest": None,
    }

    _v2 = {
        "responseId": REQUEST_ID,
        "timestamp": REQUEST_TIMESTAMP,
        "queryResult": {
            "queryText": "my zodiac sign is virgo",
            "action": "GetZodiacHoroscopeIntent",
            "allRequiredParamsPresent": True,
            "parameters": {"ZodiacSign": "virgo"},
            "intent": {
                "name": INTENT_ID,
                "webhookState": "true",
                "displayName": INTENT_NAME,
            },
            "fulfillment": {"text": "", "messages": [{"type": 0, "speech": ""}]},
            "intentDetectionConfidence": 1,
        },
        "status": {"code": 200, "errorType": "success"},
        "session": SESSION_ID,
        "originalDetectIntentRequest": None,
    }

    @property
    def v1(self):
        return copy.deepcopy(self._v1)

    @property
    def v2(self):
        return copy.deepcopy(self._v2)


Data = _Data()


async def test_v1_data() -> None:
    """Test for version 1 api based on message."""
    assert dialogflow.get_api_version(Data.v1) == 1


async def test_v2_data() -> None:
    """Test for version 2 api based on message."""
    assert dialogflow.get_api_version(Data.v2) == 2


async def test_intent_action_incomplete_v1(fixture) -> None:
    """Test when action is not completed."""
    mock_client, webhook_id = fixture
    data = Data.v1
    data["result"]["actionIncomplete"] = True

    response = await mock_client.post(
        f"/api/webhook/{webhook_id}", data=json.dumps(data)
    )
    assert response.status == HTTPStatus.OK
    assert await response.text() == ""


async def test_intent_action_incomplete_v2(fixture) -> None:
    """Test when action is not completed."""
    mock_client, webhook_id = fixture
    data = Data.v2
    data["queryResult"]["allRequiredParamsPresent"] = False

    response = await mock_client.post(
        f"/api/webhook/{webhook_id}", data=json.dumps(data)
    )
    assert response.status == HTTPStatus.OK
    assert await response.text() == ""


async def test_intent_slot_filling_v1(fixture) -> None:
    """Test when Dialogflow asks for slot-filling return none."""
    mock_client, webhook_id = fixture

    data = Data.v1
    data["result"].update(
        resolvedQuery="my zodiac sign is",
        speech="",
        actionIncomplete=True,
        parameters={"ZodiacSign": ""},
        contexts=[
            {
                "name": CONTEXT_NAME,
                "parameters": {"ZodiacSign.original": "", "ZodiacSign": ""},
                "lifespan": 2,
            },
            {
                "name": "tests_ha_dialog_context",
                "parameters": {"ZodiacSign.original": "", "ZodiacSign": ""},
                "lifespan": 2,
            },
            {
                "name": "tests_ha_dialog_params_zodiacsign",
                "parameters": {"ZodiacSign.original": "", "ZodiacSign": ""},
                "lifespan": 1,
            },
        ],
        fulfillment={
            "speech": "What is the ZodiacSign?",
            "messages": [{"type": 0, "speech": "What is the ZodiacSign?"}],
        },
        score=0.77,
    )
    data["result"]["metadata"].update(webhookForSlotFillingUsed="true")

    response = await mock_client.post(
        f"/api/webhook/{webhook_id}", data=json.dumps(data)
    )
    assert response.status == HTTPStatus.OK
    assert await response.text() == ""


async def test_intent_request_with_parameters_v1(fixture) -> None:
    """Test a request with parameters."""
    mock_client, webhook_id = fixture
    data = Data.v1
    response = await mock_client.post(
        f"/api/webhook/{webhook_id}", data=json.dumps(data)
    )
    assert response.status == HTTPStatus.OK
    text = (await response.json()).get("speech")
    assert text == "You told us your sign is virgo."


async def test_intent_request_with_parameters_v2(fixture) -> None:
    """Test a request with parameters."""
    mock_client, webhook_id = fixture
    data = Data.v2
    response = await mock_client.post(
        f"/api/webhook/{webhook_id}", data=json.dumps(data)
    )
    assert response.status == HTTPStatus.OK
    text = (await response.json()).get("fulfillmentText")
    assert text == "You told us your sign is virgo."


async def test_intent_request_with_parameters_but_empty_v1(fixture) -> None:
    """Test a request with parameters but empty value."""
    mock_client, webhook_id = fixture
    data = Data.v1
    data["result"].update(parameters={"ZodiacSign": ""})
    response = await mock_client.post(
        f"/api/webhook/{webhook_id}", data=json.dumps(data)
    )
    assert response.status == HTTPStatus.OK
    text = (await response.json()).get("speech")
    assert text == "You told us your sign is ."


async def test_intent_request_with_parameters_but_empty_v2(fixture) -> None:
    """Test a request with parameters but empty value."""
    mock_client, webhook_id = fixture
    data = Data.v2
    data["queryResult"].update(parameters={"ZodiacSign": ""})
    response = await mock_client.post(
        f"/api/webhook/{webhook_id}", data=json.dumps(data)
    )
    assert response.status == HTTPStatus.OK
    text = (await response.json()).get("fulfillmentText")
    assert text == "You told us your sign is ."


async def test_intent_request_without_slots_v1(hass: HomeAssistant, fixture) -> None:
    """Test a request without slots."""
    mock_client, webhook_id = fixture
    data = Data.v1
    data["result"].update(
        resolvedQuery="where are we",
        action="WhereAreWeIntent",
        parameters={},
        contexts=[],
    )

    response = await mock_client.post(
        f"/api/webhook/{webhook_id}", data=json.dumps(data)
    )
    assert response.status == HTTPStatus.OK
    text = (await response.json()).get("speech")

    assert text == "Anne Therese is at unknown and Paulus is at unknown"

    hass.states.async_set("device_tracker.paulus", "home")
    hass.states.async_set("device_tracker.anne_therese", "home")

    response = await mock_client.post(
        f"/api/webhook/{webhook_id}", data=json.dumps(data)
    )
    assert response.status == HTTPStatus.OK
    text = (await response.json()).get("speech")
    assert text == "You are both home, you silly"


async def test_intent_request_without_slots_v2(hass: HomeAssistant, fixture) -> None:
    """Test a request without slots."""
    mock_client, webhook_id = fixture
    data = Data.v2
    data["queryResult"].update(
        queryText="where are we",
        action="WhereAreWeIntent",
        parameters={},
        outputContexts=[],
    )

    response = await mock_client.post(
        f"/api/webhook/{webhook_id}", data=json.dumps(data)
    )
    assert response.status == HTTPStatus.OK
    text = (await response.json()).get("fulfillmentText")

    assert text == "Anne Therese is at unknown and Paulus is at unknown"

    hass.states.async_set("device_tracker.paulus", "home")
    hass.states.async_set("device_tracker.anne_therese", "home")

    response = await mock_client.post(
        f"/api/webhook/{webhook_id}", data=json.dumps(data)
    )
    assert response.status == HTTPStatus.OK
    text = (await response.json()).get("fulfillmentText")
    assert text == "You are both home, you silly"


async def test_intent_request_calling_service_v1(
    fixture, calls: list[ServiceCall]
) -> None:
    """Test a request for calling a service.

    If this request is done async the test could finish before the action
    has been executed. Hard to test because it will be a race condition.
    """
    mock_client, webhook_id = fixture
    data = Data.v1
    data["result"]["action"] = "CallServiceIntent"
    call_count = len(calls)
    response = await mock_client.post(
        f"/api/webhook/{webhook_id}", data=json.dumps(data)
    )
    assert response.status == HTTPStatus.OK
    assert len(calls) == call_count + 1
    call = calls[-1]
    assert call.domain == "test"
    assert call.service == "dialogflow"
    assert call.data.get("entity_id") == ["switch.test"]
    assert call.data.get("hello") == "virgo"


async def test_intent_request_calling_service_v2(
    fixture, calls: list[ServiceCall]
) -> None:
    """Test a request for calling a service.

    If this request is done async the test could finish before the action
    has been executed. Hard to test because it will be a race condition.
    """
    mock_client, webhook_id = fixture
    data = Data.v2
    data["queryResult"]["action"] = "CallServiceIntent"
    call_count = len(calls)
    response = await mock_client.post(
        f"/api/webhook/{webhook_id}", data=json.dumps(data)
    )
    assert response.status == HTTPStatus.OK
    assert len(calls) == call_count + 1
    call = calls[-1]
    assert call.domain == "test"
    assert call.service == "dialogflow"
    assert call.data.get("entity_id") == ["switch.test"]
    assert call.data.get("hello") == "virgo"


async def test_intent_with_no_action_v1(fixture) -> None:
    """Test an intent with no defined action."""
    mock_client, webhook_id = fixture
    data = Data.v1
    del data["result"]["action"]
    assert "action" not in data["result"]
    response = await mock_client.post(
        f"/api/webhook/{webhook_id}", data=json.dumps(data)
    )
    assert response.status == HTTPStatus.OK
    text = (await response.json()).get("speech")
    assert text == "You have not defined an action in your Dialogflow intent."


async def test_intent_with_no_action_v2(fixture) -> None:
    """Test an intent with no defined action."""
    mock_client, webhook_id = fixture
    data = Data.v2
    del data["queryResult"]["action"]
    assert "action" not in data["queryResult"]
    response = await mock_client.post(
        f"/api/webhook/{webhook_id}", data=json.dumps(data)
    )
    assert response.status == HTTPStatus.OK
    text = (await response.json()).get("fulfillmentText")
    assert text == "You have not defined an action in your Dialogflow intent."


async def test_intent_with_unknown_action_v1(fixture) -> None:
    """Test an intent with an action not defined in the conf."""
    mock_client, webhook_id = fixture
    data = Data.v1
    data["result"]["action"] = "unknown"
    response = await mock_client.post(
        f"/api/webhook/{webhook_id}", data=json.dumps(data)
    )
    assert response.status == HTTPStatus.OK
    text = (await response.json()).get("speech")
    assert text == "This intent is not yet configured within Home Assistant."


async def test_intent_with_unknown_action_v2(fixture) -> None:
    """Test an intent with an action not defined in the conf."""
    mock_client, webhook_id = fixture
    data = Data.v2
    data["queryResult"]["action"] = "unknown"
    response = await mock_client.post(
        f"/api/webhook/{webhook_id}", data=json.dumps(data)
    )
    assert response.status == HTTPStatus.OK
    text = (await response.json()).get("fulfillmentText")
    assert text == "This intent is not yet configured within Home Assistant."
