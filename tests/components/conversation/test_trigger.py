"""Test conversation triggers."""
import pytest
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import trigger
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service
from tests.typing import WebSocketGenerator


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.fixture(autouse=True)
async def setup_comp(hass):
    """Initialize components."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})


async def test_if_fires_on_event(hass: HomeAssistant, calls, setup_comp) -> None:
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
                    "data_template": {"data": "{{ trigger }}"},
                },
            }
        },
    )

    service_response = await hass.services.async_call(
        "conversation",
        "process",
        {
            "text": "Ha ha ha",
        },
        blocking=True,
        return_response=True,
    )
    assert service_response["response"]["speech"]["plain"]["speech"] == "Done"

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["data"] == {
        "alias": None,
        "id": "0",
        "idx": "0",
        "platform": "conversation",
        "sentence": "Ha ha ha",
        "slots": {},
        "details": {},
    }


async def test_response(hass: HomeAssistant, setup_comp) -> None:
    """Test the firing of events."""
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


async def test_subscribe_trigger_does_not_interfere_with_responses(
    hass: HomeAssistant, setup_comp, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that subscribing to a trigger from the websocket API does not interfere with responses."""
    websocket_client = await hass_ws_client()
    await websocket_client.send_json(
        {
            "id": 5,
            "type": "subscribe_trigger",
            "trigger": {"platform": "conversation", "command": ["test sentence"]},
        }
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
    hass: HomeAssistant, calls, setup_comp
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
                    "data_template": {"data": "{{ trigger }}"},
                },
            }
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

    # Only triggers once
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["data"] == {
        "alias": None,
        "id": "0",
        "idx": "0",
        "platform": "conversation",
        "sentence": "hello",
        "slots": {},
        "details": {},
    }


async def test_same_sentence_multiple_triggers(
    hass: HomeAssistant, calls, setup_comp
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
                        "data_template": {"data": "{{ trigger }}"},
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
                        "data_template": {"data": "{{ trigger }}"},
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
    assert len(calls) == 2

    # The calls may come in any order
    call_datas: set[tuple[str, str, str]] = set()
    for call in calls:
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


async def test_wildcards(hass: HomeAssistant, calls, setup_comp) -> None:
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
                    "data_template": {"data": "{{ trigger }}"},
                },
            }
        },
    )

    await hass.services.async_call(
        "conversation",
        "process",
        {
            "text": "play the white album by the beatles",
        },
        blocking=True,
    )

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["data"] == {
        "alias": None,
        "id": "0",
        "idx": "0",
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
    }
