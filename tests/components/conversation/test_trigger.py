"""Test conversation triggers."""

import logging

import pytest
import voluptuous as vol

from homeassistant.components.conversation import default_agent
from homeassistant.components.conversation.const import DATA_DEFAULT_ENTITY
from homeassistant.components.conversation.models import ConversationInput
from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.helpers import trigger
from homeassistant.setup import async_setup_component

from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True)
async def setup_comp(hass: HomeAssistant) -> None:
    """Initialize components."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})


async def test_if_fires_on_event(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the firing of events."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {
                    "platform": "conversation",
                    "command": [
                        "Hey yo",
                        "Ha ha ha",
                    ],
                },
                "action": {
                    "service": "test.automation",
                    "data": {
                        "data": {
                            "alias": "{{ trigger.alias }}",
                            "id": "{{ trigger.id }}",
                            "idx": "{{ trigger.idx }}",
                            "platform": "{{ trigger.platform }}",
                            "sentence": "{{ trigger.sentence }}",
                            "slots": "{{ trigger.slots }}",
                            "details": "{{ trigger.details }}",
                            "device_id": "{{ trigger.device_id }}",
                            "user_input": "{{ trigger.user_input }}",
                        }
                    },
                },
            }
        },
    )
    context = Context()
    service_response = await hass.services.async_call(
        "conversation",
        "process",
        {"text": "Ha ha ha"},
        blocking=True,
        return_response=True,
        context=context,
    )
    assert service_response["response"]["speech"]["plain"]["speech"] == "Done"

    await hass.async_block_till_done()
    assert len(service_calls) == 2
    assert service_calls[1].domain == "test"
    assert service_calls[1].service == "automation"
    assert service_calls[1].data["data"] == {
        "alias": None,
        "id": 0,
        "idx": 0,
        "platform": "conversation",
        "sentence": "Ha ha ha",
        "slots": {},
        "details": {},
        "device_id": None,
        "user_input": {
            "agent_id": None,
            "context": context.as_dict(),
            "conversation_id": None,
            "device_id": None,
            "language": "en",
            "text": "Ha ha ha",
        },
    }


async def test_response(hass: HomeAssistant) -> None:
    """Test the conversation response action."""
    response = "I'm sorry, Dave. I'm afraid I can't do that"
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {
                    "platform": "conversation",
                    "command": ["Open the pod bay door Hal"],
                },
                "action": {
                    "set_conversation_response": response,
                },
            }
        },
    )

    service_response = await hass.services.async_call(
        "conversation",
        "process",
        {
            "text": "Open the pod bay door Hal",
        },
        blocking=True,
        return_response=True,
    )
    assert service_response["response"]["speech"]["plain"]["speech"] == response


async def test_empty_response(hass: HomeAssistant) -> None:
    """Test the conversation response action with an empty response."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {
                    "platform": "conversation",
                    "command": ["Open the pod bay door Hal"],
                },
                "action": {
                    "set_conversation_response": "",
                },
            }
        },
    )

    service_response = await hass.services.async_call(
        "conversation",
        "process",
        {
            "text": "Open the pod bay door Hal",
        },
        blocking=True,
        return_response=True,
    )
    assert service_response["response"]["speech"]["plain"]["speech"] == ""


async def test_response_same_sentence(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the conversation response action with multiple triggers using the same sentence."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "trigger": {
                        "id": "trigger1",
                        "platform": "conversation",
                        "command": ["test sentence"],
                    },
                    "action": [
                        # Add delay so this response will not be the first
                        {"delay": "0:0:0.100"},
                        {
                            "service": "test.automation",
                            "data_template": {
                                "data": {
                                    "alias": "{{ trigger.alias }}",
                                    "id": "{{ trigger.id }}",
                                    "idx": "{{ trigger.idx }}",
                                    "platform": "{{ trigger.platform }}",
                                    "sentence": "{{ trigger.sentence }}",
                                    "slots": "{{ trigger.slots }}",
                                    "details": "{{ trigger.details }}",
                                    "device_id": "{{ trigger.device_id }}",
                                    "user_input": "{{ trigger.user_input }}",
                                }
                            },
                        },
                        {"set_conversation_response": "response 2"},
                    ],
                },
                {
                    "trigger": {
                        "id": "trigger2",
                        "platform": "conversation",
                        "command": ["test sentence"],
                    },
                    "action": {"set_conversation_response": "response 1"},
                },
            ]
        },
    )
    context = Context()
    service_response = await hass.services.async_call(
        "conversation",
        "process",
        {"text": "test sentence"},
        blocking=True,
        return_response=True,
        context=context,
    )
    await hass.async_block_till_done()

    # Should only get first response
    assert service_response["response"]["speech"]["plain"]["speech"] == "response 1"

    # Service should still have been called
    assert len(service_calls) == 2
    assert service_calls[1].domain == "test"
    assert service_calls[1].service == "automation"
    assert service_calls[1].data["data"] == {
        "alias": None,
        "id": "trigger1",
        "idx": 0,
        "platform": "conversation",
        "sentence": "test sentence",
        "slots": {},
        "details": {},
        "device_id": None,
        "user_input": {
            "agent_id": None,
            "context": context.as_dict(),
            "conversation_id": None,
            "device_id": None,
            "language": "en",
            "text": "test sentence",
        },
    }


async def test_response_same_sentence_with_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the conversation response action with multiple triggers using the same sentence and an error."""
    caplog.set_level(logging.ERROR)
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "trigger": {
                        "id": "trigger1",
                        "platform": "conversation",
                        "command": ["test sentence"],
                    },
                    "action": [
                        # Add delay so this will not finish first
                        {"delay": "0:0:0.100"},
                        {"service": "fake_domain.fake_service"},
                    ],
                },
                {
                    "trigger": {
                        "id": "trigger2",
                        "platform": "conversation",
                        "command": ["test sentence"],
                    },
                    "action": {"set_conversation_response": "response 1"},
                },
            ]
        },
    )
    context = Context()
    service_response = await hass.services.async_call(
        "conversation",
        "process",
        {"text": "test sentence"},
        blocking=True,
        return_response=True,
        context=context,
    )
    await hass.async_block_till_done()

    # Should still get first response
    assert service_response["response"]["speech"]["plain"]["speech"] == "response 1"

    # Error should have been logged
    assert "Error executing script" in caplog.text


async def test_subscribe_trigger_does_not_interfere_with_responses(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that subscribing to a trigger from the websocket API does not interfere with responses."""
    websocket_client = await hass_ws_client()
    await websocket_client.send_json_auto_id(
        {
            "type": "subscribe_trigger",
            "trigger": {"platform": "conversation", "command": ["test sentence"]},
        }
    )
    await websocket_client.receive_json()

    service_response = await hass.services.async_call(
        "conversation",
        "process",
        {
            "text": "test sentence",
        },
        blocking=True,
        return_response=True,
    )

    # Default response, since no automations with responses are registered
    assert service_response["response"]["speech"]["plain"]["speech"] == "Done"

    # Now register a trigger with a response
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation test1": {
                "trigger": {
                    "platform": "conversation",
                    "command": ["test sentence"],
                },
                "action": {
                    "set_conversation_response": "test response",
                },
            }
        },
    )

    service_response = await hass.services.async_call(
        "conversation",
        "process",
        {
            "text": "test sentence",
        },
        blocking=True,
        return_response=True,
    )

    # Response will now come through
    assert service_response["response"]["speech"]["plain"]["speech"] == "test response"


async def test_same_trigger_multiple_sentences(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test matching of multiple sentences from the same trigger."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {
                    "platform": "conversation",
                    "command": ["hello", "hello[ world]"],
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {
                        "data": {
                            "alias": "{{ trigger.alias }}",
                            "id": "{{ trigger.id }}",
                            "idx": "{{ trigger.idx }}",
                            "platform": "{{ trigger.platform }}",
                            "sentence": "{{ trigger.sentence }}",
                            "slots": "{{ trigger.slots }}",
                            "details": "{{ trigger.details }}",
                            "device_id": "{{ trigger.device_id }}",
                            "user_input": "{{ trigger.user_input }}",
                        }
                    },
                },
            }
        },
    )
    context = Context()
    await hass.services.async_call(
        "conversation",
        "process",
        {
            "text": "hello",
        },
        blocking=True,
        context=context,
    )

    # Only triggers once
    await hass.async_block_till_done()
    assert len(service_calls) == 2
    assert service_calls[1].domain == "test"
    assert service_calls[1].service == "automation"
    assert service_calls[1].data["data"] == {
        "alias": None,
        "id": 0,
        "idx": 0,
        "platform": "conversation",
        "sentence": "hello",
        "slots": {},
        "details": {},
        "device_id": None,
        "user_input": {
            "agent_id": None,
            "context": context.as_dict(),
            "conversation_id": None,
            "device_id": None,
            "language": "en",
            "text": "hello",
        },
    }


async def test_same_sentence_multiple_triggers(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test use of the same sentence in multiple triggers."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "trigger": {
                        "id": "trigger1",
                        "platform": "conversation",
                        "command": [
                            "hello",
                        ],
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "data": {
                                "alias": "{{ trigger.alias }}",
                                "id": "{{ trigger.id }}",
                                "idx": "{{ trigger.idx }}",
                                "platform": "{{ trigger.platform }}",
                                "sentence": "{{ trigger.sentence }}",
                                "slots": "{{ trigger.slots }}",
                                "details": "{{ trigger.details }}",
                                "device_id": "{{ trigger.device_id }}",
                                "user_input": "{{ trigger.user_input }}",
                            }
                        },
                    },
                },
                {
                    "trigger": {
                        "id": "trigger2",
                        "platform": "conversation",
                        "command": [
                            "hello[ world]",
                        ],
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "data": {
                                "alias": "{{ trigger.alias }}",
                                "id": "{{ trigger.id }}",
                                "idx": "{{ trigger.idx }}",
                                "platform": "{{ trigger.platform }}",
                                "sentence": "{{ trigger.sentence }}",
                                "slots": "{{ trigger.slots }}",
                                "details": "{{ trigger.details }}",
                                "device_id": "{{ trigger.device_id }}",
                                "user_input": "{{ trigger.user_input }}",
                            }
                        },
                    },
                },
            ],
        },
    )

    await hass.services.async_call(
        "conversation",
        "process",
        {
            "text": "hello",
        },
        blocking=True,
    )

    await hass.async_block_till_done()
    assert len(service_calls) == 3

    # The calls may come in any order
    call_datas: set[tuple[str, str, str]] = set()
    service_calls.pop(0)  # First call is the call to conversation.process
    for call in service_calls:
        call_data = call.data["data"]
        call_datas.add((call_data["id"], call_data["platform"], call_data["sentence"]))

    assert call_datas == {
        ("trigger1", "conversation", "hello"),
        ("trigger2", "conversation", "hello"),
    }


@pytest.mark.parametrize(
    "command",
    ["hello?", "hello!", "4 a.m."],
)
async def test_fails_on_punctuation(hass: HomeAssistant, command: str) -> None:
    """Test that validation fails when sentences contain punctuation."""
    with pytest.raises(vol.Invalid):
        await trigger.async_validate_trigger_config(
            hass,
            [
                {
                    "id": "trigger1",
                    "platform": "conversation",
                    "command": [
                        command,
                    ],
                },
            ],
        )


@pytest.mark.parametrize(
    "command",
    [""],
)
async def test_fails_on_empty(hass: HomeAssistant, command: str) -> None:
    """Test that validation fails when sentences are empty."""
    with pytest.raises(vol.Invalid):
        await trigger.async_validate_trigger_config(
            hass,
            [
                {
                    "id": "trigger1",
                    "platform": "conversation",
                    "command": [
                        command,
                    ],
                },
            ],
        )


async def test_fails_on_no_sentences(hass: HomeAssistant) -> None:
    """Test that validation fails when no sentences are provided."""
    with pytest.raises(vol.Invalid):
        await trigger.async_validate_trigger_config(
            hass,
            [
                {
                    "id": "trigger1",
                    "platform": "conversation",
                    "command": [],
                },
            ],
        )


async def test_wildcards(hass: HomeAssistant, service_calls: list[ServiceCall]) -> None:
    """Test wildcards in trigger sentences."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {
                    "platform": "conversation",
                    "command": [
                        "play {album} by {artist}",
                    ],
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {
                        "data": {
                            "alias": "{{ trigger.alias }}",
                            "id": "{{ trigger.id }}",
                            "idx": "{{ trigger.idx }}",
                            "platform": "{{ trigger.platform }}",
                            "sentence": "{{ trigger.sentence }}",
                            "slots": "{{ trigger.slots }}",
                            "details": "{{ trigger.details }}",
                            "device_id": "{{ trigger.device_id }}",
                            "user_input": "{{ trigger.user_input }}",
                        }
                    },
                },
            }
        },
    )

    context = Context()
    await hass.services.async_call(
        "conversation",
        "process",
        {
            "text": "play the white album by the beatles",
        },
        blocking=True,
        context=context,
    )

    await hass.async_block_till_done()
    assert len(service_calls) == 2
    assert service_calls[1].domain == "test"
    assert service_calls[1].service == "automation"
    assert service_calls[1].data["data"] == {
        "alias": None,
        "id": 0,
        "idx": 0,
        "platform": "conversation",
        "sentence": "play the white album by the beatles",
        "slots": {
            "album": "the white album",
            "artist": "the beatles",
        },
        "details": {
            "album": {
                "name": "album",
                "text": "the white album",
                "value": "the white album",
            },
            "artist": {
                "name": "artist",
                "text": "the beatles",
                "value": "the beatles",
            },
        },
        "device_id": None,
        "user_input": {
            "agent_id": None,
            "context": context.as_dict(),
            "conversation_id": None,
            "device_id": None,
            "language": "en",
            "text": "play the white album by the beatles",
        },
    }


async def test_trigger_with_device_id(hass: HomeAssistant) -> None:
    """Test that a trigger receives a device_id."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {
                    "platform": "conversation",
                    "command": ["test sentence"],
                },
                "action": {
                    "set_conversation_response": "{{ trigger.device_id }}",
                },
            }
        },
    )

    agent = hass.data[DATA_DEFAULT_ENTITY]
    assert isinstance(agent, default_agent.DefaultAgent)

    result = await agent.async_process(
        ConversationInput(
            text="test sentence",
            context=Context(),
            conversation_id=None,
            device_id="my_device",
            language=hass.config.language,
            agent_id=None,
        )
    )
    assert result.response.speech["plain"]["speech"] == "my_device"
